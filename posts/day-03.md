---
title: Android 面试学习 Day 3｜扩展函数、委托、高阶函数
tags: [Android, Kotlin, 面试, 知识星球]
created: 2026-07-29
updated: 2026-08-10
sources:
  - https://kotlinlang.org/docs/extensions.html
  - https://kotlinlang.org/docs/delegation.html
  - https://kotlinlang.org/docs/lambdas.html
day: 3
---

# Android 面试学习 Day 3｜扩展函数、委托、高阶函数

> 导语：今天三个特性都指向同一件事——「在不改原类源码、不写样板的前提下，表达更多」。扩展给现成类加方法，委托把样板交给别人，高阶函数把「行为」当参数传。它们是 Kotlin 表达力的核心。

## 今天学到了什么

1. 扩展函数/属性：给任意类型「附加」方法，**静态解析，不修改原类**。
2. 委托（`by`）：把属性/接口实现的样板代码交给一个委托对象。
3. 高阶函数：接收或返回函数的函数；配合 lambda，是函数式风格的根基。

## 直观解释

**画面一：扩展函数是「站在原类旁边喊它干活」**

你没法改 `String` 的源码，但你可以在它旁边写「`String.shout()`」——调用时像 `tom.shout()`，仿佛 String 多了个方法。但实际上 String 类一行没动，这个 `shout()` 是一个**静态函数**，第一个参数就是接收者。

```kotlin
fun String.shout() = this.uppercase() + "!"

println("tom".shout())   // TOM!
```

**画面二：委托是「把脏活外包」**

```kotlin
// 属性委托：lazy 把「懒加载」这个通用模式外包出去
val config by lazy { loadConfig() }

// 接口委托：把实现外包给一个已有对象
class ListImpl(list: List<String>) : List<String> by list
```

不用自己手写 `getList()` 转发那一堆样板，`by` 一个词搞定。

**画面三：高阶函数是「把行为当快递寄」**

```kotlin
fun repeat3(action: () -> Unit) {   // 接收一个「无参无返回的函数」
    repeat(3) { action() }
}
repeat3 { println("hi") }            // 寄过去一个 lambda
```

`{ println("hi") }` 就是一个被当作参数传递的代码块。标准库的 `map`/`filter`/`forEach` 全是这个套路。

## 核心原理

### 扩展函数的本质（面试必考）

扩展函数**不是真的给类加方法**。它编译成一个**静态函数**，第一个参数是接收者类型：

```kotlin
fun String.shout() = uppercase()
// 编译后等价于：
// static String shout(String receiver) { return receiver.uppercase() }
```

两个直接推论：

1. **静态解析**：调用哪个扩展函数，由**编译时接收者的声明类型**决定，不是运行时实际类型。所以扩展**不能被子类覆盖**（没有虚分派）。

```kotlin
open class Animal
class Dog : Animal()

fun Animal.info() = "animal"
fun Dog.info() = "dog"

val a: Animal = Dog()
println(a.info())   // animal！按声明类型 Animal 解析
```

2. **不能访问私有成员**：扩展函数不在类内部，只能访问 public 成员。

### 扩展函数 vs 成员函数

如果一个类已经有同名同参的成员函数，成员函数优先。扩展函数只是「补丁」，不会覆盖原有行为。

### 委托的两类

**类/接口委托** `interface X by impl`：把接口的所有方法实现转发给 `impl`，只覆写你关心的几个。

**属性委托** `val x by Delegate`：把 get/set 逻辑外包。标准库内置几个常用委托：`lazy`（懒加载）、`observable`（赋值时回调）、`vetoable`（赋值前可否决）、`map`（用 Map 当属性存储）。

### 高阶函数与函数类型

函数类型语法：`(Int, String) -> Boolean` 表示「接收 Int 和 String，返回 Boolean」。

```kotlin
fun <T> List<T>.filter(predicate: (T) -> Boolean): List<T> {
    val result = mutableListOf<T>()
    for (e in this) if (predicate(e)) result.add(e)
    return result
}

listOf(1, 2, 3).filter { it > 1 }   // { it > 1 } 是 predicate
```

lambda 里的 `it` 是单参数默认名。高阶函数配合 lambda 的开销问题（额外对象分配、虚调用）会在 Day 4 的 `inline` 解决。

## Kotlin/Android 示例

```kotlin
// 1. 扩展：给 View 加 visible/gone
fun View.visible() { visibility = View.VISIBLE }
fun View.gone() { visibility = View.GONE }

// 使用
button.visible()

// 2. 委托：ViewModel 里用 observable 监听变化
class FormViewModel : ViewModel() {
    var name: String by observable("") { _, _, newValue ->
        validate(newValue)
    }
}

// 3. 高阶函数：封装「耗时任务 + 回切主线程」
fun <T> Activity.runOnUi(block: () -> T, onResult: (T) -> Unit) {
    // ... 异步执行 block，完成后 onResult
}
```

## 常见误区

1. **「扩展函数能被重写」**：不能。静态解析，按声明类型决定，没有多态分派。
2. **「扩展能访问私有成员」**：不能，只能访问 public。
3. **「扩展会修改原类字节码」**：不会，它只是编译成静态函数。
4. **「`by lazy` 是字段」**：`lazy` 是属性委托，背后是个 `Lazy<T>` 对象，第一次 get 时执行初始化块。
5. **「高阶函数传 lambda 没有开销」**：有。lambda 会变成匿名对象（除非 inline，见 Day 4）。在性能敏感路径要注意。

## 面试回答

> **Q：扩展函数本质是什么？能被子类覆盖吗？**
> 扩展函数编译成一个静态函数，第一个参数是接收者类型，不修改原类。调用哪个扩展由**编译时接收者的声明类型**决定（静态解析），没有虚分派，所以**不能被子类覆盖**。成员函数优先于同名扩展函数。

> **Q：什么是委托？举几个标准库的属性委托？**
> 委托把属性 get/set 或接口方法实现转发给另一个对象。标准库属性委托：`lazy`（懒加载）、`observable`（赋值回调）、`vetoable`（赋值前否决）、Map（用 Map 存属性）。类委托用 `interface X by impl`，把接口实现转发给 impl，只覆写关心的方法。

> **Q：高阶函数是什么？lambda 在 JVM 上怎么表示？**
> 高阶函数是接收或返回函数的函数。函数类型如 `(T) -> Boolean`。lambda 在 JVM 上通常编译成 `FunctionN` 接口的匿名对象，会有对象分配和虚调用开销；`inline`（Day 4）可以把高阶函数的内联展开，消除这个开销。

## 今日练习

1. 给 `String` 写一个 `isEmail()` 扩展函数，给 `Int` 写一个 `isPositive` 扩展属性。
2. 用接口委托 `by` 把一个 `MutableList` 包装成只读外观，只覆写 `get`。
3. 写一个高阶函数 `inline fun <T> T.applyIf(cond: Boolean, block: T.() -> Unit): T`，体会 lambda 接收者（`T.() -> Unit`）和普通 lambda 的区别。
4. 验证「扩展静态解析」：定义 `Animal`/`Dog` 继承链和同名扩展，把 `Dog` 赋给 `Animal` 变量后调用扩展，观察结果。

## 下一节预告

Day 4：`inline`、`noinline`、`crossinline`、`reified`——解开高阶函数性能开销和非局部返回的谜题，理解为什么 `reified` 必须配 `inline`。

---

## 摘要（200 字以内）

Day 3 学三个表达力特性。扩展函数本质是「接收者作首参的静态函数」，不修改原类，静态解析（按声明类型），不能被子类覆盖，不能访问私有成员，成员函数优先于同名扩展。委托用 `by` 把样板外包：接口委托转发方法实现，属性委托转发 get/set（标准库有 lazy/observable/vetoable/Map）。高阶函数接收或返回函数，lambda 在 JVM 上是 FunctionN 匿名对象，有分配开销（Day 4 的 inline 解决）。三者共同点是「不改原类、不写样板，表达更多」。

## 标签

#Kotlin #扩展函数 #委托 #高阶函数 #Android面试
