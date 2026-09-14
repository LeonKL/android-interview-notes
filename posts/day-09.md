---
title: Android 面试学习 Day 9｜协程取消、超时与异常处理
tags: [Android, Kotlin, 面试, 知识星球]
created: 2026-08-31
updated: 2026-09-14
sources:
  - https://kotlinlang.org/docs/cancellation-and-timeouts.html
  - https://kotlinlang.org/docs/exception-handling.html
day: 9
---

# Android 面试学习 Day 9｜协程取消、超时与异常处理

> 导语：取消和异常是协程的第二道分水岭。本篇建立三个画面：取消是「贴收工通知」而非「拔电源」；`CancellationException` 是正常下班而非事故；异常在普通作用域「整层疏散」，在 `SupervisorJob` 下「独立分区」。

## 今天学到了什么

1. 取消是**协作式**的：`cancel()` 只置状态，真正退出发生在挂起点（抛 `CancellationException`）或 `isActive`/`ensureActive()`/`yield()` 检查处。
2. `CancellationException` 是「正常取消」信号；`catch (Exception)` 会把它拦下，捕获后必须重抛。
3. 取消后 `finally` 会执行，但其中不能挂起；需要挂起的清理（回滚、关连接）包 `withContext(NonCancellable)`。
4. `withTimeout` 超时抛 `TimeoutCancellationException`，`withTimeoutOrNull` 返回 null；超时同样受协作式约束。
5. `launch` 和 `async` 的异常**都**向父传播并连带取消兄弟；「不 `await` 就吞异常」只在脱离结构化并发时成立；`await()` 会重抛原异常。
6. `SupervisorJob` 隔离兄弟失败；`viewModelScope`/`lifecycleScope` 内置 `SupervisorJob + Main.immediate`；`CoroutineExceptionHandler` 只对根 `launch` 生效。

## 直观解释

**画面一：收工通知。** `job.cancel()` 不是拔电源，是给 Job 贴一张「请尽快收工」的通知。协程要走到能看到通知的地方（挂起点：`delay`/`yield`/`await`/`withContext`）才会真正退出；埋头干活的纯 CPU 循环看不见通知，会一直跑完。

**画面二：正常下班。** 协程被取消时通过抛 `CancellationException` 退出，框架把它当作正常流程。真正的错误是用 `catch (Exception)` 把「下班通知」拦下来不让走——破坏取消机制才是事故。

**画面三：消防分区。** 普通 Job 下，一个子协程失败像火警拉响整层疏散：父被取消、所有兄弟连带取消、火情逐层上报。`SupervisorJob` 把楼层隔成独立分区：一间房着火不烧邻居，但火警仍然上报（交给异常处理器）。

## 核心原理

### 协作式取消与 CPU 循环

```kotlin
val job = scope.launch(Dispatchers.Default) {
    var sum = 0L
    for (i in 1..1_000_000_000) { sum += i }   // 无挂起点：cancel() 拦不住
}
```

修法是主动检查：循环内 `if (!isActive) throw CancellationException(...)` 或周期性 `yield()`。三个工具：`isActive`（布尔）、`ensureActive()`（不活跃即抛）、`yield()`（让出线程并检查）。

### CancellationException 必须重抛

JVM 上它是 `java.util.concurrent.CancellationException` 的别名，继承自 `RuntimeException`，会被 `catch (Exception)` 一并捕获。吞掉它，协程就「赖着不走」。正确写法：

```kotlin
try { doWork() }
catch (e: CancellationException) { throw e }   // 放行取消
catch (e: Exception) { log(e) }                // 只处理真正的错误
```

### 清理：finally 与 NonCancellable

`finally` 里的普通代码会执行；但协程已在取消中，其中的**挂起调用会立刻再抛** `CancellationException`。需要挂起的清理用 `withContext(NonCancellable) { db.rollback(); resource.close() }`——只用于清理，不要拿来抵抗取消继续干活。

### 超时

`withTimeout(2000) { ... }` 的实现是启动定时取消：到点取消块内协程并抛 `TimeoutCancellationException`（`CancellationException` 子类）。块内无挂起点同样拦不住；要优雅降级用 `withTimeoutOrNull`，它超时返回 null。

### 异常传播的精确规则

1. `launch`：未捕获异常立刻传播给父 Job → 父取消所有子 → 逐层上抛，根作用域交给 `CoroutineExceptionHandler` 或默认处理器（Android 默认闪退）。
2. `async`：在结构化作用域内，失败**立即**向父传播并取消兄弟——不等你 `await`；`await()` 把原异常重抛给调用方。只有脱离结构化并发（如 `GlobalScope.async` 且无人等待）时，异常才存在 `Deferred` 里等待 `await` 取出，永不 `await` 才会丢失。
3. `coroutineScope { }`：等所有子完成，任一子失败则整个作用域失败（取消其余子，向调用方抛出异常）；多子同时失败会收到聚合异常。

### SupervisorJob 与 CoroutineExceptionHandler

`SupervisorJob` 下子失败不取消父和兄弟（分区隔离）；但向下传播保留——supervisor 自己被取消时子连带取消。`supervisorScope { }` 是作用域构建器版本。`CoroutineExceptionHandler` 只对**根 launch 协程**的未捕获异常生效；装在子协程上无效（异常被父截走），对 `async` 无效（异常经 `await` 暴露）。

### Android 现实：viewModelScope 为什么「烧不死」

`viewModelScope` = `SupervisorJob() + Dispatchers.Main.immediate`（`lifecycleScope` 同理）：一个请求失败只死自己，兄弟继续。但 SupervisorJob 只挡「兄弟连带取消」，**挡不住崩溃本身**——未捕获异常仍走默认处理器，Android 上照样闪退，业务层仍要自己 catch。

## Kotlin 示例

```kotlin
// 1. 需要挂起清理的取消安全写法
val job = scope.launch {
    try {
        workWith(resource)
    } catch (e: CancellationException) {
        throw e
    } finally {
        withContext(NonCancellable) { db.rollback() }
    }
}

// 2. 验证 async 异常不等 await 就传播
coroutineScope {
    val d = async { throw RuntimeException("boom") }
    delay(100)   // 无人 await，但 coroutineScope 仍失败，兄弟被取消
}

// 3. 分区隔离
val scope = CoroutineScope(SupervisorJob() + CoroutineExceptionHandler { _, e -> log(e) })
scope.launch { throw A() }   // 只取消自己，兄弟照常
scope.launch { work() }
```

## 常见误区

1. **「cancel() 立即杀死协程」**——协作式，无挂起点的代码不会响应。
2. **「catch (Exception) 统一处理就行」**——吞掉取消信号；必须单独放行 `CancellationException`。
3. **「async 不 await 异常就没了」**——只在无父的场景成立；结构化作用域内立即向父传播。
4. **「SupervisorJob 能防止崩溃」**——只防兄弟连带取消，不防未捕获异常闪退。
5. **「CEH 装在哪个协程都行」**——只对根 launch 生效，对 async 无效。
6. **「finally 里能做一切清理」**——挂起调用需 `NonCancellable` 包裹。

## 面试回答

> **Q：cancel() 后协程立即停止吗？**
> 不会。取消是协作式：`cancel()` 置状态，退出发生在挂起点或主动检查处；纯 CPU 循环必须自插检查点（`isActive`/`ensureActive`/`yield`）。

> **Q：launch 和 async 的异常传播区别？**
> 两者都向父传播（结构化并发）。`launch` 直接触发父取消；`async` 同样立即传播（不等 await），且 `await()` 重抛原异常；「不 await 就吞」仅 `GlobalScope.async` 等无父场景成立。

> **Q：SupervisorJob 解决什么问题？**
> 子失败不连带取消父和兄弟；向下传播保留。`viewModelScope` 内置它，所以单请求失败不影响其他请求——但未捕获异常仍会闪退，业务层要自己 catch 并放行 `CancellationException`。

> **Q：为什么 finally 里做挂起清理会失败？**
> 协程已在取消中，finally 里的挂起调用立刻再抛 `CancellationException`；清理用 `withContext(NonCancellable)`。

## 今日练习

1. `job.cancel()` 后，finally 里的 `println` 会执行吗？`delay(100)` 呢？为什么不同？
2. 把上题改成「取消后必须回滚数据库」，写出正确代码。
3. `withTimeoutOrNull(1000) { 无挂起点的循环 }` 超时后会发生什么？
4. `coroutineScope` 里两个 `async`，一个失败且从未 `await`——作用域正常结束还是失败？兄弟如何？
5. `viewModelScope` 里两个 `launch`，一个抛 `IOException` 未捕获：另一个会取消吗？应用会崩吗？

## 下一节预告

Day 10：结构化并发——`Job` 父子关系全模型、`coroutineScope`/`supervisorScope` 的选择策略、取消与异常沿树传播全图。

---

## 摘要（200 字以内）

Day 9 攻克取消与异常。取消是协作式：cancel() 只置状态，退出发生在挂起点或 isActive/ensureActive/yield 检查处，CPU 循环须自插检查点。CancellationException 是正常取消信号，catch 后必须重抛；finally 里的挂起清理要包 NonCancellable。withTimeout 本质是定时取消，抛 TimeoutCancellationException。异常传播：launch 立即上抛父级；async 在结构化作用域内同样立即传播并取消兄弟，await 重抛，「不 await 就吞」仅无父场景成立。SupervisorJob 分区隔离兄弟失败（viewModelScope 内置），但挡不住未捕获异常闪退；CEH 只对根 launch 生效。

## 标签

#Kotlin #协程 #取消 #异常处理 #Android面试
