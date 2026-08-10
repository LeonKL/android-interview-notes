---
title: Android 面试学习 Day 5｜泛型、in/out、类型擦除与星投影
tags: [Android, Kotlin, 面试, 知识星球]
created: 2026-08-06
updated: 2026-08-10
sources:
  - https://kotlinlang.org/docs/generics.html
  - https://kotlinlang.org/docs/inline-functions.html#reified-type-parameters
day: 5
---

# Android 面试学习 Day 5｜泛型、in/out、类型擦除与星投影

> 导语：泛型是 Kotlin 系列难度跳跃最大的一节。核心问题其实只有一个：「`Box<Int>` 能不能塞进 `Box<Number>`？」整个型变体系都在回答这个。今天用费曼的方式，先把画面建起来。

## 今天学到了什么

1. 泛型默认是「不变」：`Box<Int>` 不是 `Box<Number>` 的子类型。
2. `out` 协变（只读生产者）、`in` 逆变（只写消费者）——对应 Java 的 PECS，但 Kotlin 做进声明处语法。
3. 类型擦除：运行时 `List<Int>` 和 `List<String>` 是同一个类；`reified` 是破局（承接 Day 4）。
4. 星投影 `<*>`：未知类型的协变投影，只能读不能写。

## 直观解释

**画面一：泛型是「带类型标签的盒子模板」**

`Box<T>` 是一个模板，`T` 是占位符。`Box<Int>` 和 `Box<String>` 是两个**不同**的成品盒子，标签不同——它们之间没有继承关系，哪怕 Int 是 Number 的子类。

**画面二：型变三态——「只读/只写/读写」**

```
不变（默认）：能读能写 → 类型必须严格匹配
协变 out：    只读（只生产 T）→ 子类型关系顺着走：Box<Int> 是 Box<Number> 子类型
逆变 in：     只写（只消费 T）→ 子类型关系反向：Sink<Number> 是 Sink<Int> 子类型
```

记忆：PECS 在 Kotlin 里就是 **Consumer in, Producer out**（官方原话）。

**画面三：类型擦除像「出厂撕掉标签」**

编译期 `List<Int>`、`List<String>` 标签清清楚楚，编译器严格检查；但编译完运行时，标签被撕了，只剩裸 `List`。所以你没法在运行时 `if (x is List<Int>)`——运行时根本看不出装的什么。

**画面四：星投影是「我不知道装什么，但保证类型安全」**

`List<*>` 是「装某种未知类型的列表」，读出来只能当 `Any?`，写入直接禁止。它不是 `List<Any>`——后者明确说装 Any，前者是「不知道装啥」。

## 核心原理

### 不变（Invariant）的默认与原因

```kotlin
val n: Box<Number> = Box<Int>(42)   // ❌ 编译错误
```

为什么禁止？如果允许，`n.set(3.14)` 就能把 Double 塞进「实际装 Int 的盒子」，类型系统破裂。**读写都有的容器必须严格类型匹配**——这是默认不变的根本原因。

### 声明处型变（Kotlin 的关键改进）

Java 是**使用处**型变（每次用都写 `? extends`/`? super`）。Kotlin 在**声明处**指定：

```kotlin
interface Source<out T> {        // 协变：T 只出现在返回位置
    fun next(): T
}
val s: Source<Number> = Source<Int>()   // ✅ 合法

interface Sink<in T> {           // 逆变：T 只出现在参数位置
    fun consume(t: T)
}
val s: Sink<Int> = Sink<Number>()  // ✅ 合法：能吃 Number 的池子当然能吃 Int
```

官方规则原文：
> 当类 C 的类型参数 T 声明为 `out`，T 只能出现在 C 成员的 out 位置（返回值），作为回报 `C<Base>` 可以安全地成为 `C<Derived>` 的超类型。

### PECS / Producer out, Consumer in

- 你要从容器**读** T（生产者）→ 用 `out T`。
- 你要往容器**写** T（消费者）→ 用 `in T`。
- 既要读又要写 → 不变。

标准库：`List<out T>`（只读，协变）；`MutableList<T>`（不变，因为读写都有）；`Comparator<in T>`（逆变）。

### 类型擦除（承接 Day 4 reified）

Kotlin/JVM 泛型运行时擦除。官方原文：
> 「运行时泛型类型的实例不保留实际类型参数信息，称为类型擦除。」

后果：`if (x is List<String>)` 编译错误；`listOf<Int>().javaClass == listOf<String>().javaClass` 为 true。

破局：`inline fun <reified T>` 让编译器在调用点把真实类型填进来（Day 4 已学）。代价是只能用在 inline 函数。

### 星投影 `<*>` 的精确语义

官方规则：
- 对 `Foo<out T : TUpper>`：`Foo<*>` 等价于 `Foo<out TUpper>`——可安全读出 `TUpper`。
- 对 `Foo<in T>`：`Foo<*>` 等价于 `Foo<in Nothing>`——什么都不能安全写。
- 对不变 `Foo<T : TUpper>`：`Foo<*>` 读时当 `out TUpper`、写时当 `in Nothing`。

所以 `MutableList<*>` 能读（当 Any?）但不能 add——因为写位置是 `in Nothing`。

`<*>` vs `<Any>` 区别：`List<Any>` 明确装 Any，可写（若是 Mutable）；`List<*>` 是「未知类型」，只能读、不能写。

## Kotlin/Android 示例

```kotlin
// 1. 协变的生产者
interface Producer<out T> { fun next(): T }
class IntProducer : Producer<Int> { override fun next() = 42 }
val p: Producer<Number> = IntProducer()   // ✅

// 2. 逆变的消费者
interface Action<in T> { fun execute(t: T) }
class AnyAction : Action<Any> {
    override fun execute(t: Any) { println(t) }
}
val a: Action<Int> = AnyAction()   // ✅ 能处理 Any 的当然能处理 Int

// 3. reified 跳过擦除
inline fun <reified T> List<*>.filterByType(): List<T> =
    filter { it is T } as List<T>

// 4. 星投影：只关心数量不关心类型
fun count(list: List<*>) = list.size   // 读不出具体类型，但能数数
```

## 常见误区

1. **「`List<Int>` 是 `List<Number>` 的子类型」**：不是，List 默认不变。只有 `List<out T>` 协变后才行（Kotlin 的 `List` 确实声明了 `out T`，所以 `List<Int>` 是 `List<Number>` 子类型；但 `MutableList` 不行）。
2. **「`MutableList` 能协变」**：不能，它读写都有，必须不变，否则会塞错类型。
3. **「`List<*>` 和 `List<Any>` 一样」**：不一样。前者是「未知类型」，只能读成 Any? 不能写；后者明确装 Any，可写。
4. **「reified 能用在普通函数」**：不能，必须 inline（Day 4）。
5. **「泛型擦除了所以完全不安全」**：编译期检查仍严格，只是运行时拿不到类型参数信息。

## 面试回答

> **Q：Kotlin `in`/`out` 和 Java 通配符什么关系？**
> `out T` ≈ `? extends T`（只读生产者），`in T` ≈ `? super T`（只写消费者）。区别是 Kotlin 在**声明处**指定型变（`class Box<out T>`），Java 只能在**使用处**写通配符。声明处型变让 API 更干净，调用方不用反复写通配符。

> **Q：为什么 `MutableList` 不能协变？**
> 它既要读又要写。如果协变，`MutableList<Int>` 就能当 `MutableList<Number>`，然后 `add(3.14)` 会把 Double 塞进装 Int 的列表，运行时 ClassCastException。可变容器必须不变，这是保证类型安全的根本。

> **Q：`reified` 为什么必须配 `inline`？**
> 泛型擦除后运行时没有 T 的信息。`inline` 把调用点展开，编译器在调用点知道 T 的真实类型，`reified` 把它填进函数体，`is T`/`as T` 才成立。普通函数没有这个展开机制，拿不到类型信息。

> **Q：`List<*>` 和 `List<Any>` 区别？**
> `List<*>` 是「未知类型的列表」，元素读出来是 Any?，不能写（写位置是 in Nothing）；`List<Any>` 是「明确装 Any 的列表」，可写。型变语义上 `List<*>` ≈ `List<out Any?>`。

## 今日练习

1. 写一个协变的 `Producer<out T>`，并说明它的方法签名为什么安全。
2. 解释 `Array<Any>` 不能接收 `Array<Int>`（提示：JVM 数组是协变的，这是个历史坑）。
3. 解释 `inline fun <reified T> Gson.fromJson(json): T` 为什么能写，普通函数不行。
4. `Map<String, *>` 能不能 `put`？为什么？

## 下一节预告

Day 6：Java 互操作、平台类型、Kotlin 编译产物——把今天的类型擦除和型变放进混编场景，看 Kotlin 和 Java 互相调用会发生什么。

---

## 摘要（200 字以内）

Day 5 攻克型变。泛型默认「不变」——`Box<Int>` 不是 `Box<Number>` 子类型，因为读写都有的容器必须严格匹配。Kotlin 用声明处型变改进 Java 使用处通配符：`out T` 协变（T 只在返回位置，生产者），`in T` 逆变（T 只在参数位置，消费者），口诀 Producer out / Consumer in。`MutableList` 因读写都有必须不变。类型擦除让运行时拿不到类型参数，`reified` 配 `inline` 靠调用点展开破局（承接 Day 4）。星投影 `List<*>` 是「未知类型」的安全投影，读成 Any? 不能写，与明确装 Any 的 `List<Any>` 不同。

## 标签

#Kotlin #泛型 #型变 #类型擦除 #Android面试
