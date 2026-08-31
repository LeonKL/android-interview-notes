---
title: Android 面试学习 Day 8｜协程基础：suspend、CoroutineScope、launch/async 与调度器
tags: [Android, Kotlin, 面试, 知识星球]
created: 2026-08-10
updated: 2026-08-10
sources:
  - https://kotlinlang.org/docs/coroutines-guide.html
  - https://kotlinlang.org/docs/coroutines-basics.html
  - https://kotlinlang.org/docs/coroutine-context-and-dispatchers.html
day: 8
---

# Android 面试学习 Day 8｜协程基础：suspend、CoroutineScope、launch/async 与调度器

> 导语：进入 Week 2 协程篇。本篇建立三个心智模型：协程是什么、挂起怎么工作、如何启动与调度；并修正一批流传很广的误述，为取消与异常打地基。

## 今天学到了什么

1. 协程是「可挂起、可恢复」的计算单元，运行在线程上但不独占线程；它提升的是**并发吞吐**，不是单任务速度。
2. `suspend` 只声明「可能挂起」，不切线程、也不保证任何特定线程；线程由 `CoroutineContext` 的 Dispatcher 决定。
3. `CoroutineScope` 把协程取消绑定到生命周期；`GlobalScope` 可以手动取消，但缺少生命周期管理。
4. `launch` 返回 `Job`（可 `join`/`cancel`/查 `isActive`），`async` 返回 `Deferred` 供 `await` 取结果。
5. `Dispatchers.IO` 与 `Default` 共享底层线程池；`withContext` 恢复的是原 `CoroutineContext`，不保证回到同一线程。

## 直观解释

**画面一：收银台。** `Thread.sleep` 是收银员数钱时干等一秒，后面客人全堵着；`delay` 是把当前客人的订单夹到夹子上（Continuation），立刻叫下一位，一分钟后那位客人带着订单从断点继续。协程的收益在「等待」期间不占线程，所以一个线程能并发挂着大量协程。

**画面二：暂停键。** `suspend` 是函数上一个合法的「可能按暂停」标记。按暂停时，局部变量和「下一步执行哪行」存进 `Continuation`，协程离开线程；恢复时取出现场续跑。

**画面三：家族树。** 每个协程都属于一个作用域：父作用域取消，子协程连带取消。`GlobalScope` 启动的协程不是「无法取消」——它返回 `Job`，可以手动 `cancel()`；问题是它不绑定任何生命周期，没有父作用域兜底，容易泄漏或操作已销毁的对象。

**画面四：两种单据。** `launch` 领的是「任务单」（`Job`）——做副作用和流程编排，做得完等得起，随时可叫停；`async` 领的是「提货单」（`Deferred<T>`）——凭单取货（`await()`）。

## 核心原理

### suspend 与线程无关

```kotlin
lifecycleScope.launch {          // 默认 Dispatchers.Main
    greet()                      // 打印 main 线程
}
lifecycleScope.launch(Dispatchers.IO) {
    greet()                      // 同一个 greet，打印 IO 线程
}
```

`suspend` 约束的是挂起语义，不约束线程。反过来，`suspend` 函数里写阻塞调用（`Thread.sleep`、同步 IO）会**老老实实占住当前线程**——要后台执行必须显式 `withContext(Dispatchers.IO)`。

### 状态机与 Continuation

编译器把 `suspend` 函数变换成状态机：每个挂起点是一个状态分支，现场存在 `Continuation` 里；挂起时保存状态、返回挂起标记、释放线程；恢复时按 `Continuation` 记录的位置跳回继续。这就是「挂起不阻塞线程」的底层机制。于是单线程可挂十万协程各自 `delay` 而不崩。

### 作用域一览

| Scope | 绑定 | 自动取消时机 |
|---|---|---|
| `lifecycleScope` | Activity/Fragment | DESTROYED |
| `viewModelScope` | ViewModel | onCleared() |
| `coroutineScope {}` | 调用者（结构化并发） | 块结束 |
| `GlobalScope` | 无 | 手动 cancel / 进程结束 |
| `runBlocking {}` | 当前线程 | 块结束 |

`runBlocking` 真的阻塞当前线程：`main()` 和 JVM 测试里合法；Android 主线程上用会 ANR。但不宜一刀切说「生产代码必是 bug」——判断标准是**被阻塞的线程能否承受这个阻塞**。

### launch、async 与 Job

```kotlin
val job = scope.launch {
    repeat(100) { i ->
        if (!isActive) return@launch   // 协作式取消：响应取消请求
        println("work $i")
        delay(50)
    }
}
job.cancel()   // 请求取消（协作式，不是立即杀死）
job.join()     // 挂起，等它真正结束
```

取消是协作式的：协程在挂起点或主动检查 `isActive` 时才会响应。`async` 用于要结果的计算，两个 `async` 同时启动时总耗时 ≈ max 而非相加。**关于 async 异常的误述**：「不 `await` 异常就被吞掉」并不准确——在结构化作用域里，`async` 的异常默认会向父 Job 传播并取消兄弟协程，`await()` 时再重抛一次；完整规则（SupervisorJob 等）Day 9 展开。

### 调度器与 withContext

| Dispatcher | 底层 | 并行度 |
|---|---|---|
| Main | 平台主线程 | 1 |
| IO | 与 Default 共享池 | 弹性，默认上限 64（可配） |
| Default | 与 IO 共享池 | max(2, CPU 核数) |
| Unconfined | 不固定 | 极少用 |

`withContext(Dispatchers.IO) { ... }` 在进入块时切到 IO，离开块时**恢复进入前的 `CoroutineContext`**（含原 Dispatcher）——如果原来在 Main 就回 Main；但它不承诺回到同一个线程对象。对比 `launch(Dispatchers.IO)`：后者启动新的子协程，不等待、也不切回，当前协程立刻继续往下走。

## Kotlin/Android 示例：MVVM + Repository

```kotlin
class UserRepository(private val api: UserApi) {
    // 阻塞式 API 显式切 IO；若 api.getUser 本身是 suspend，则无需再包
    suspend fun fetchUser(id: String): User =
        withContext(Dispatchers.IO) { api.getUser(id) }
}

class UserViewModel(private val repo: UserRepository) : ViewModel() {
    private val _uiState = MutableStateFlow<UiState>(UiState.Loading)

    fun load(id: String) {
        viewModelScope.launch {                    // 绑定 VM 生命周期
            try {
                val user = async { repo.fetchUser(id) }
                val config = async { repo.fetchConfig() }
                _uiState.value = UiState.Success(user.await(), config.await())
            } catch (e: Exception) {
                _uiState.value = UiState.Error(e)  // 哪些 catch 得住：Day 9
            }
        }
    }
}
```

贯穿：Scope 生命周期绑定、suspend、`withContext` 切线程、`async` 并发合并、协作式取消。

## 常见误区

1. **「协程比线程快」**——单任务不更快；收益在等待期不占线程，提升并发吞吐。CPU 密集任务用协程无加速。
2. **「suspend 就是切后台」**——不切线程；阻塞调用会占住当前线程。
3. **「GlobalScope 无法取消」**——可以手动 `cancel()`；真正的问题是缺生命周期绑定。
4. **「launch 是发后不管」**——`Job` 可 `join`/`cancel`，且受父作用域管理，只是不返回业务结果。
5. **「async 不 await 异常就没了」**——结构化作用域里异常会向父传播；`await` 重抛。
6. **「withContext 完回到同一线程」**——恢复的是原 `CoroutineContext`，线程由 Dispatcher 再分配。

## 面试回答

> **Q：协程是什么，和线程什么关系？**
> （结论）协程是可挂起恢复的计算单元，运行在线程上但不独占线程。
> （机制）挂起时现场存进 `Continuation` 并释放线程，恢复时续跑；用顺序代码表达异步逻辑。
> （代价）收益在等待期不占线程，提升并发吞吐而非单任务速度；CPU 密集无加速。

> **Q：suspend 函数会切线程吗？**
> 不会。`suspend` 只声明可能挂起，线程由 Dispatcher 决定；`suspend` 里写阻塞调用会占住当前线程，须显式 `withContext(IO)`。

> **Q：launch 和 async 区别？**
> `launch` 返回 `Job`，用于副作用与流程编排；`async` 返回 `Deferred<T>`，`await()` 取结果。异常都按结构化并发规则向父传播，`await` 会重抛。

> **Q：withContext 和 launch(IO) 有什么不同？**
> `withContext` 临时切换、顺序执行、结束恢复原上下文；`launch(IO)` 启动新协程并发执行，不影响当前协程继续运行。

## 今日练习

1. 预测下面输出的顺序与线程名，再运行验证：
   ```kotlin
   runBlocking {
       launch { println("A ${Thread.currentThread().name}") }
       println("B ${Thread.currentThread().name}")
       val d = async { delay(100); println("C"); 42 }
       println("D ${d.await()}")
   }
   ```
2. 改错：`GlobalScope.launch(Dispatchers.Main)` 里调用同步网络再更新 `textView`——指出问题并改写。
3. `fetchUser` → `fetchAvatar(user.id)` → `fetchConfig()` 顺序加载，其中 config 独立，改成并发。
4. CPU 密集循环被 `cancel()` 后不能立刻停下，为什么？改成能及时响应取消的版本。

## 下一节预告

Day 9：协程取消与异常处理——`CancellationException`、`try/finally` 与 `SupervisorJob`，本篇留下的「async 异常」「协作式取消」在那里展开。

---

## 摘要（200 字以内）

Day 8 建立协程地基。协程是可挂起恢复的计算单元，挂起时现场存进 Continuation 并释放线程，收益是并发吞吐而非单任务速度。suspend 不切线程也不保证特定线程，阻塞调用须显式 withContext(IO)。Scope 把取消绑定生命周期：GlobalScope 可手动取消但缺生命周期管理；runBlocking 在 main/测试合法，判断标准是被阻塞线程能否承受。launch 返回 Job（join/cancel/isActive 协作式取消），async 返回 Deferred 并发合并；「不 await 就吞异常」是误述。Dispatchers.IO 与 Default 共享底层池；withContext 恢复原 CoroutineContext，不保证同一线程。

## 标签

#Kotlin #协程 #suspend #Android面试 #Dispatchers
