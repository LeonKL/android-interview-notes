---
title: Android 面试学习 Day 6｜Java 互操作、平台类型、Kotlin 编译产物
tags: [Android, Kotlin, 面试, 知识星球]
created: 2026-08-07
updated: 2026-08-10
sources:
  - https://kotlinlang.org/docs/java-interop.html
  - https://kotlinlang.org/docs/java-to-kotlin-interop.html
  - https://kotlinlang.org/docs/java-to-kotlin-nullability-guide.html
day: 6
---

# Android 面试学习 Day 6｜Java 互操作、平台类型、Kotlin 编译产物

> 导语：许多存量 Android 项目仍包含 Java/Kotlin 混编代码。今天讲两件混编最容易踩坑的事：Kotlin 的「空安全破洞」——平台类型；以及 Kotlin 语法糖编译成 JVM 字节码后的样子（`object`/`companion`/`data class`/`suspend` 各自的产物）。

## 今天学到了什么

1. 平台类型 `T!`：Java 返回值的可空性未知，是混编项目 NPE 的重要风险来源之一。
2. Kotlin 调 Java：属性访问、SAM 转换、关键字转义。
3. Java 调 Kotlin：顶层函数→文件类、`@JvmOverloads`/`@JvmField`/`@JvmStatic` 三件套。
4. 编译产物：`data class`/`object`/`companion`/`suspend` 在字节码层面的样子。

## 直观解释

**画面一：平台类型是「可空性贴了问号的箱子」**

Java 没有空安全概念，返回值可能 null 也可能不 null。Kotlin 接收时不知道是 `String` 还是 `String?`，于是标记成 `String!`——「不确定」。
这个「不确定」绕过了编译期检查：你可以把它赋给非空 `String`，编译器放行；但 Java 真返回 null 时，运行时 NPE。这是 Kotlin 空安全在混编中的重要风险边界之一。

**画面二：编译产物是「语法糖背后的真相」**

Kotlin 的 `object`、`companion object`、`data class`、`suspend` 在 JVM 字节码层面都是「普通类 + 静态字段 + 方法」的组合。理解了产物，你才真正理解这些语法糖「到底是什么」。

## 核心原理

### 平台类型（Platform Types）

官方原文：
> 「Java 中任何引用都可能为 null，对来自 Java 的对象强制 Kotlin 的严格空安全是不切实际的。Java 声明的类型在 Kotlin 中被视为不可表示类型（non-denotable），称为平台类型。」

记号：`T!` 表示「T 或 T?」，IDE 提示里会看到。

危险之处——直接后果：
> 「如果你赋给非空类型变量而运行时实际为 null，Kotlin 抛 NullPointerException。」

```kotlin
// Java: public String getName() { return null; }
val n: String = java.getName()   // 编译通过，运行时 NPE
val s: String? = java.getName()  // 安全
val u = java.getName()           // 平台类型 String!，调用 .length 放行但 null 会崩
```

### Kotlin 识别的空性注解

官方列举：JetBrains `@Nullable/@NotNull`、JSpecify、AndroidX/Android Support、JSR-305（`javax.annotation`）、FindBugs、Eclipse、Lombok、RxJava 3、Vert.x。加了注解后，Kotlin 按 Java 类型按注解当作真可空/非空处理，不再当平台类型。

### Kotlin 调 Java 的常见映射

- **属性访问**：Java 的 `getX()/setX()` 在 Kotlin 里直接当属性 `p.x` / `p.x = ...`。布尔 `isX()` 访问为 `p.x`（去掉 is）。
- **SAM 转换**：Java 单抽象方法接口，Kotlin 可直接传 lambda：`setListener { x -> ... }`。
- **关键字转义**：Java 方法叫 `in()`，Kotlin 调 `foo.`in`()`。
- **操作符映射**：`add(E)` 在 Kotlin 可用 `+=`。

### Java 调 Kotlin 的三件套

- **顶层函数**：`StringUtils.kt` 里的 `fun foo()` 编译成 `StringUtilsKt.foo()`。`@file:JvmName("Strings")` 改类名。
- **`@JvmOverloads`**：为带默认参数的函数生成重载，让 Java 也能省略参数（Android 高频：自定义 View 构造）。
- **`@JvmField`**：暴露为公开字段，不走 getter/setter。
- **`@JvmStatic`**：`companion object`/`object` 的方法生成真静态转发，Java 直接 `Foo.bar()` 而非 `Foo.Companion.bar()`。

### 编译产物（语法糖背后的真相）

- **`object Singleton`** → 一个类 + `public static final INSTANCE` 字段，构造私有。Java 调 `Singleton.INSTANCE.bar()`。
- **`companion object`** → 外部类里的静态内部类 `Companion`，外部类持有其实例。Java 调 `Outer.Companion.bar()`，加 `@JvmStatic` 后额外生成 `Outer.bar()`。
- **`data class User(val name, val age)`** → 构造 + getName/getAge + equals/hashCode（基于主构造属性）+ toString + copy + component1/component2。**类体里单独声明的属性不参与 equals**。
- **`suspend fun foo()`** → 签名变成 `Object foo(Continuation c)`。Java 不能当普通函数调用，这是协程互操作的主要障碍（Day 8 起讲协程）。
- **可空类型** → JVM 层面就是裸 `T`，可空性编译后擦除（只在 `@Metadata` 注解里）。这也是平台类型问题的根源。

## Kotlin/Android 示例

```kotlin
// 1. 平台类型防御
class UserRepo(private val javaApi: JavaApi) {
    // ❌ 危险：可能 NPE
    // fun name(): String = javaApi.getName()

    // ✅ 显式标可空
    fun name(): String? = javaApi.getName()
    // 或加注解 @Nullable String getName() 让 Kotlin 识别
}

// 2. 自定义 View 用 @JvmOverloads 省重载
class MyView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyle: Int = 0
) : View(context, attrs, defStyle)

// 3. 给 Java 调用方做友好封装
object Api {
    @JvmStatic
    fun init() { /* ... */ }
}

class User(val name: String) {
    companion object {
        @JvmStatic
        fun create(name: String) = User(name)
    }
}
```

## 常见误区

1. **「Kotlin 项目 100% 空安全」**：纯 Kotlin 项目 NPE 大幅减少，但并非绝对为零（`!!`、显式抛出等场景仍可能出现）；混编场景下平台类型是重要的 NPE 风险来源之一。
2. **「平台类型就是 `Any`」**：不是。它是「可空性未知」的不可表示类型，IDE 显示为 `T!`。
3. **「`object` 在类加载时初始化」**：object declaration 是首次**访问**时懒初始化（Day 2 已学）；companion object 才是类加载时初始化。
4. **「`data class` equals 基于所有字段」**：只基于主构造属性，类体内字段不参与。
5. **「Java 能直接调 Kotlin 协程 suspend 函数」**：不能，签名变成 `foo(Continuation)`，需要适配层（Day 8 详述）。

## 面试回答

> **Q：Kotlin 空安全在混编项目为什么「打折」？**
> Java 没有 `?` 概念，Kotlin 把 Java 返回值推断为平台类型 `T!`（可空性未知），绕过编译期空检查；赋给非空类型时编译通过，但 Java 真返回 null 就可能在运行时 NPE。平台类型是混编项目 NPE 的重要风险来源之一（不是唯一来源，`!!`、显式抛出等也会导致）。防御：显式标可空、在 Java 侧加 `@Nullable/@NonNull` 注解让 Kotlin 按真实可空性识别（Kotlin 支持 JetBrains/AndroidX/JSR-305 等多种注解）。

> **Q：Java 怎么调 Kotlin 顶层函数？**
> 编译成「文件类」`XxxKt`，Java 调 `XxxKt.foo()`。用 `@file:JvmName("X")` 改类名。默认参数 Java 看不到，要加 `@JvmOverloads` 才生成对应重载。

> **Q：`@JvmOverloads` 干嘛的？**
> 为带默认参数的 Kotlin 函数生成对应数量的重载，让 Java 调用方也能省略参数。典型用例是 Android 自定义 View 构造函数（4 个重载变一个）。

> **Q：`object` 单例在字节码里是什么？**
> 一个类 + 一个 `public static final INSTANCE` 字段，Java 通过 `Singleton.INSTANCE` 访问。`companion object` 则是外部类里的静态内部类，持有 Companion 实例，加 `@JvmStatic` 才额外生成静态转发。

## 今日练习

1. 解释 `val s: String = javaMethod()` 在 Java 返回 null 时为什么崩，给出两种修法。
2. `Util.kt` 里 `fun foo()`，Java 怎么调？怎么让类名变成 `Util` 而不是 `UtilKt`？
3. `class MyView @JvmOverloads constructor(ctx, attrs, defStyle = 0)` 会生成几个构造函数？
4. `object App` 加 `@JvmStatic` 和 `companion object` 加 `@JvmStatic`，Java 调用方式分别是什么？
5. 为什么说协程 `suspend` 函数对 Java 互操作不友好？

## 下一节预告

Day 7：Kotlin 综合复习与面试表达——把 Day 1～6 串成「编译期安全 + 表达力 + 互操作」三条主线，练习「结论先行」的面试答题框架。

---

## 摘要（200 字以内）

Day 6 讲混编。平台类型 `T!` 是 Java 返回值在 Kotlin 里的「可空性未知」标记，绕过编译期空检查，赋给非空类型时编译放行、运行时若为 null 则 NPE——它是混编项目 NPE 的重要风险来源之一（非唯一来源）。防御靠显式标可空，或在 Java 侧加 @Nullable/@NonNull 注解让 Kotlin 按真实可空性识别（Kotlin 支持 JetBrains/AndroidX/JSR-305 等）。Kotlin 调 Java 享属性访问和 SAM 转换；Java 调 Kotlin 用三件套 @JvmOverloads/@JvmField/@JvmStatic。编译产物：object → 类+INSTANCE 字段，companion → 静态内部类，data class → 基于主构造属性的 equals，suspend → foo(Continuation) 签名（协程互操作障碍）。

## 标签

#Kotlin #Java互操作 #平台类型 #编译产物 #Android面试
