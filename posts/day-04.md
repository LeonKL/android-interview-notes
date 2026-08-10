---
title: Android 面试学习 Day 4｜inline、noinline、crossinline、reified
tags: [Android, Kotlin, 面试, 知识星球]
created: 2026-08-03
updated: 2026-08-10
sources:
  - https://kotlinlang.org/docs/inline-functions.html
  - https://kotlinlang.org/docs/generics.html#reified-type-parameters
day: 4
---

# Android 面试学习 Day 4｜inline、noinline、crossinline、reified

> 导语：Day 3 说高阶函数传 lambda 有对象分配开销。今天的 `inline` 就是来填这个坑的，顺便解锁 `reified`——让被擦除的泛型类型「失而复得」。四个关键字都围绕同一个机制：编译期把函数体复制到调用点。

## 今天学到了什么

1. `inline`：把函数体和传入的 lambda **复制到调用点**，消除 lambda 对象分配和虚调用开销。
2. `noinline`：局部关闭内联，让某个 lambda 仍作为对象存在。
3. `crossinline`：禁止某个 lambda 的非局部返回（用于它会跑在别的执行上下文）。
4. `reified`：让泛型类型参数在函数内部可被 `is`/`as` 检查，**必须配 `inline`**。

## 直观解释

**画面一：inline 是「把快递直接送到家」**

普通高阶函数传 lambda：lambda 被打包成一个匿名对象，送到函数里，函数用完再扔——每次调用都打一个包。
`inline`：编译器不打包，直接把 lambda 的内容**抄到调用处**，像快递员直接把货搬进你家，没有包装盒。

```kotlin
inline fun <T> repeat(times: Int, action: (Int) -> T) {
    for (i in 0 until times) action(i)
}

// 调用
repeat(3) { println(it) }
// 编译后近似于：
// for (i in 0 until 3) println(i)
```

没有 lambda 对象，没有虚调用——性能开销没了。

**画面二：noinline 是「这个包裹必须原样寄」**

有时你不想让某个 lambda 被内联（比如要存起来、传给别的不可内联的代码）。`noinline` 告诉编译器：「这个 lambda 别展开，留作对象」。

**画面三：reified 是「让被擦除的泛型重新显形」**

Java/Kotlin 泛型在运行时被擦除——`List<Int>` 运行时只是 `List`，你没法写 `if (x is List<Int>)`。但 `reified`（配合 `inline`）能让编译器在调用点把真实类型「实体化」进去，于是 `is T`、`as T` 都能用了。

```kotlin
inline fun <reified T> Any?.isA(): Boolean = this is T

"hi".isA<String>()   // true
42.isA<String>()     // false
```

## 核心原理

### inline 的机制与代价

机制：编译器把 `inline` 函数体复制到每个调用点，传入的 lambda 也被展开。好处是消除 lambda 对象分配和函数调用开销。

代价（面试要能讲）：
1. **代码体积膨胀**：每个调用点都复制一份函数体，函数体大、调用点多时字节码明显变大。
2. **不能被当作普通函数传递**：内联函数本身就是编译期行为，不是运行时实体。
3. **公开 API 的 inline 有二进制兼容约束**：官方明确，public inline 函数不能在函数体里使用 non-public（private/internal）声明，因为内联会把实现暴露到调用模块，后续改动会造成二进制不兼容。例外是 internal 声明加 `@PublishedApi`。

### 非局部返回与 crossinline

普通 lambda 不允许裸 `return`（只能 `return@label`），因为它只是个代码块对象，没法让外层函数返回。
`inline` 函数里的 lambda **可以**裸 `return`（非局部返回），因为 lambda 被展开进了外层函数体，return 真的能返回到外层。

```kotlin
inline fun forEach(items: List<Int>, action: (Int) -> Unit) {
    for (i in items) action(i)
}

fun find(items: List<Int>): Int {
    forEach(items) {
        if (it == 5) return it   // 非局部返回：直接返回 find！
    }
    return -1
}
```

问题：如果 `inline` 函数把 lambda 放到**另一个执行上下文**（比如嵌套对象、别的线程），非局部返回就没意义甚至非法。这时用 `crossinline` 标记这个 lambda：「禁止非局部返回」。

```kotlin
inline fun runLater(crossinline action: () -> Unit) {
    val r = Runnable { action() }   // lambda 跑在 Runnable 里，不能非局部返回
}
```

`noinline` 的区别：`noinline` 是「完全不内联，留作对象」；`crossinline` 是「内联，但禁止非局部返回」。

### reified 为什么必须配 inline

泛型类型擦除后，运行时拿不到 `T`。`inline` 把调用点展开，在调用点编译器**知道** `T` 的真实类型（比如 `"hi".isA<String>()` 调用点 T 就是 String），于是 `reified` 把这个真实类型「填」进函数体，`is T` 就成立了。

官方明确：**普通（非 inline）函数不能用 reified**——因为它拿不到调用点的类型信息。这是编译期机制，不是运行时魔法。

限制：`reified` 只能在 inline 函数里用；`is T`/`as T` 在 reified 下成立，但函数本身仍受 inline 限制（不能是 open/虚函数，不能传递）。

## Kotlin/Android 示例

```kotlin
// 1. 标准 inline：let/run/apply/also/use/forEach 都是 inline
inline fun <T> T.runCatchingInline(block: T.() -> R): Result<R> = ...

// 2. reified 起跳 Fragment/Activity（Android 高频用法）
inline fun <reified T : View> Activity.find(@IdRes id: Int): T =
    findViewById<T>(id) as T     // reified 让类型推断穿透

inline fun <reified T : Fragment> FragmentActivity.push(bundle: Bundle? = null) {
    supportFragmentManager.commit {
        replace<T>(R.id.container, args = bundle)
    }
}

// 3. Gson/JSON 反序列化（reified 经典场景）
inline fun <reified T> Gson.fromJson(json: String): T =
    fromJson(json, T::class.java)   // 没法 new T()，但能拿 T::class.java

// 调用：val user: User = gson.fromJson(json)   // 不用传 User::class.java
```

## 常见误区

1. **「所有高阶函数都该加 inline」**：不是。inline 有代码膨胀代价，标准库的 inline 高阶函数大多函数体很短且调用频繁。普通业务高阶函数不必加。
2. **「inline 函数可以是 open 的」**：inline 是编译期复制，没有虚分派概念，和 `open`/继承多态冲突，不能加 `open`（用 inline 替代继承时的多态）。
3. **「reified 能用在普通函数」**：不能，必须 inline。
4. **「noinline 和 crossinline 一样」**：noinline 是「不内联、留对象」；crossinline 是「内联，但禁止非局部返回」。
5. **「inline 一定能加速」**：只在传 lambda 的高阶函数收益明显；对没传 lambda 的普通函数，inline 收益微乎其微，反而增加体积。

## 面试回答

> **Q：inline 函数做了什么？为什么需要它？**
> 它把函数体和传入的 lambda 复制到调用点，消除 lambda 对象分配和虚调用开销，并允许 lambda 非局部返回。代价是代码体积膨胀，且 public inline 函数有二进制兼容约束。适合函数体短、传 lambda、调用频繁的场景。

> **Q：noinline 和 crossinline 区别？**
> `noinline` 让某个 lambda 参数**不内联**，仍作为对象存在（便于存储、传递）；`crossinline` 让 lambda **内联，但禁止非局部返回**，用于 lambda 会在别的执行上下文（嵌套对象、Runnable 等）被调用的场景。

> **Q：reified 为什么必须配 inline？**
> 泛型类型擦除后运行时拿不到 T；`inline` 把调用点展开，编译器在调用点知道真实类型，于是 `reified` 把真实类型「填」进函数体，`is T`/`as T` 才能成立。普通函数没有这个展开机制，所以不能 reified。

## 今日练习

1. 写一个 `inline fun measure(block: () -> Unit): Long` 计时函数，调用 `measure { Thread.sleep(100) }`，理解为什么它比普通函数高效。
2. 写一个带 `crossinline` 的 `inline fun post(crossinline action: () -> Unit)`，把 action 包进 `Runnable`，尝试在 action 里写裸 `return`，观察编译错误。
3. 用 `reified` 写一个 `inline fun <reified T> List<*>.filterByType(): List<T>`，过滤出指定类型的元素。
4. 解释为什么 `inline fun foo() = privateBar()`（privateBar 是 private）在 public API 中有问题，怎么用 `@PublishedApi` 解决。

## 下一节预告

Day 5：泛型、`in/out`、类型擦除、星投影——把今天的 `reified` 放进更大的图景：为什么泛型会擦除、什么时候类型安全需要协变/逆变。

---

## 摘要（200 字以内）

Day 4 四个关键字都围绕「编译期把函数体复制到调用点」。`inline` 消除高阶函数传 lambda 的对象分配开销，代价是代码膨胀和二进制兼容约束（public inline 不能用 non-public 声明，除非 @PublishedApi）；它还允许 lambda 非局部返回。`noinline` 让某 lambda 不内联、留作对象；`crossinline` 内联但禁止非局部返回（用于 lambda 跑在别的执行上下文）。`reified` 让泛型类型在函数内可被 is/as 检查，必须配 inline——因为类型信息靠调用点展开获得，普通函数拿不到。inline 只适合函数体短、传 lambda、调用频繁的场景，不是所有高阶函数都该加。

## 标签

#Kotlin #inline #reified #泛型 #Android面试
