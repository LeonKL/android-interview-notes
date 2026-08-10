---
title: Android 面试学习 Day 1｜val/var、空安全、lateinit/lazy
tags: [Android, Kotlin, 面试, 知识星球]
created: 2026-07-27
updated: 2026-08-10
sources:
  - https://kotlinlang.org/docs/null-safety.html
  - https://kotlinlang.org/docs/properties.html
  - https://kotlinlang.org/docs/delegated-properties.html
day: 1
---

# Android 面试学习 Day 1｜val/var、空安全、lateinit/lazy

> 导语：Kotlin 把 Java 里最常见的两类崩溃——「变量被误改」和「空指针」——前移到编译期。今天建立三件事的画面：不可变引用、可空类型、延迟初始化。这是后续协程、泛型、互操作的起点。

## 今天学到了什么

1. `val` 是「引用不可变」，`var` 是「引用可变」——但 `val` 不等于「对象不可变」。
2. Kotlin 用 `?` 把类型分成「非空」和「可空」两套，空安全是**编译期**检查。
3. 延迟初始化有两把工具：`lateinit var`（先声明后赋值）和 `val by lazy`（首次访问才计算）。

## 直观解释

**画面一：val 像贴了封条的盒子**

`val x = 1` 这个盒子上贴着封条，你不能把盒子里的东西**整体换掉**（`x = 2` 不行）。但如果盒子里装的是一个可变的列表，你仍然可以往列表里加元素——封条封的是「盒子指向哪个对象」，不是「对象内部能不能改」。

```kotlin
val list = mutableListOf(1, 2)
list.add(3)    // ✅ 合法：对象内容可变
list = mutableListOf()  // ❌ 编译错误：引用不可变
```

**画面二：可空类型像「可能装着炸弹的箱子」**

`String` 是普通箱子，保证里面有字符串；`String?` 是可能装着 `null` 的箱子，编译器**不让你直接打开**，必须先确认安全（`?.`、`?:`、`!!`）。

```kotlin
var name: String = "Tom"      // 非空，保证有值
var nick: String? = null      // 可空，可能没值

println(name.length)          // ✅ 直接用
println(nick.length)          // ❌ 编译错误：可能为 null
println(nick?.length)         // ✅ 安全调用，null 时返回 null
println(nick?.length ?: 0)    // ✅ Elvis：null 时给默认 0
println(nick!!.length)        // ⚠️ 强制断言非空，null 就抛 NPE
```

**画面三：延迟初始化像「先开收据，稍后提货」**

有些字段（依赖注入的 service、生命周期回调注入的 view）在构造时还没准备好，但它们确定不会是 null。`lateinit` 给这类场景一个合法的「先声明，后赋值」通道。

```kotlin
class Activity {
    lateinit var service: UserService   // 先占位

    fun onCreate() { service = UserService() }   // 后赋值
    fun use() { service.fetch() }                 // 直接用，不用 ?.
}
```

`lazy` 则是另一种懒：「这个值计算很贵，而且可能根本用不到，那就等第一次访问时再算，并记住结果」。

```kotlin
val config: Config by lazy { loadExpensiveConfig() }   // 首次访问才调 load
```

## 核心原理

### val 的精确含义

`val` 声明的是「一个 getter」，默认实现是「返回字段」。所以严格说 `val` 是「没有 setter」，不是「值永远不变」。如果给 `val` 写自定义 getter，它的值是可以变的：

```kotlin
val timeStr: String
    get() = System.currentTimeMillis().toString()   // 每次访问都不同
```

### 空安全是编译期为主、运行时仍有辅助保障的机制

空安全的主体是**编译期检查**：编译器在编译期把「非空类型当 null 赋值」「可空类型直接解引用」都挡住，这是最核心的一层。

「编译完就没保护了」不准确，但也要分清两类东西——**运行时真正会执行的代码**和**给工具/互操作用的信息**：

**运行时真正执行的检查（实际拦截 null 的代码）**：
- **参数空检查**：对公开 API 的非空参数，编译器会在方法入口插入 `Intrinsics` 工具类的空值断言（具体方法名随编译器版本可能变化，不必记死），运行时收到 null 立即抛 `NullPointerException`（fail-fast，而不是把 null 传到深处再炸）。
- **安全调用分支**：`?.` 会在字节码里生成真实的 null 分支判断，不是「编译期就没了」。
- `!!` 也会生成显式的 null 判断，命中即抛 NPE。

**给互操作和工具用的信息（本身不执行检查）**：
- **可空性注解**（`@Nullable`/`@NotNull` 等）会被写到公开 API 的字节码里，主要作用是让 Java 调用方、其他 Kotlin 模块和静态分析工具能识别可空性。**注解本身不执行运行时检查**，它是一种「契约信息」。
- `@Metadata` 注解保存完整的 Kotlin 类型签名（含可空性），供 Kotlin 编译器跨模块识别。

所以更准确的说法是：**Kotlin 的空安全以编译期类型系统为主，运行时由编译器插入的 `Intrinsics` 断言和 `?.`/`!!` 的空值分支实际执行检查；可空性注解则是给互操作和工具传递信息，自身不做拦截**。纯 Kotlin 项目里 NPE 会显著减少，但仍可能在 `!!`、显式 `throw NullPointerException`、未初始化访问、底层互操作等场景出现。

### lateinit 的限制（容易记错）

官方规则：`lateinit` 只能用在 `var`（非 `val`）、非基本类型、非空类型上；作为类属性时**不能放在主构造函数**里、**不能有自定义 getter/setter**；可用范围是顶层属性、局部变量、类体里的属性。

访问未初始化的 `lateinit` 会抛 `UninitializedPropertyAccessException`，可以用 `this::prop.isInitialized` 先检查。

### lazy 的线程安全模式

`lazy()` 默认用 `LazyThreadSafetyMode.SYNCHRONIZED`（双检锁，只算一次）。另有 `PUBLICATION`（多线程可能都算，但只用第一个结果）和 `NONE`（单线程场景，无锁最快）。

## 常见误区

1. **「`val` 就是常量」**：错。`val` 是引用不可变，对象内容可变；真正的编译期常量是 `const val`（只能基本类型 + 顶层或 object 成员）。
2. **「`lateinit` 可以用在 `val`」**：错，只能 `var`。
3. **「`lateinit` 能用在 `Int`」**：错，不能用于基本类型（JVM 上它们有默认值 0，无法区分「未赋值」）。
4. **「`lazy` 总是线程安全」**：默认是，但 `LazyThreadSafetyMode.NONE` 不是。
5. **「`!!` 是推荐写法」**：它等于「我发誓这里不是 null，否则崩」，应该尽量用 `?.`/`?:` 替代，只在确信非空且想快速失败的局部场景用。

## 面试回答

> **Q：`val` 和 `var` 的区别？`val` 一定不可变吗？**
> `val` 是没有 setter 的属性，引用不可重新赋值；`var` 可以。但 `val` 不保证对象不可变——`val list = mutableListOf()` 仍能 `add`。带自定义 getter 的 `val` 值甚至每次访问都不同。真正的编译期常量是 `const val`。

> **Q：Kotlin 空安全怎么实现的？**
> 以编译期类型系统为主：`T` 和 `T?` 是两种类型，非空类型不能赋 null、可空类型不能直接解引用，必须用 `?.`/`?:`/`!!` 处理。运行时由编译器插入的实际检查包括：公开 API 非空参数入口的 `Intrinsics` 空值断言、`?.` 和 `!!` 生成的真实 null 分支。另外，可空性注解（`@NotNull/@Nullable` 等）会写到字节码，但它们是给 Java 调用方和静态分析工具用的**信息契约**，本身不执行运行时检查。纯 Kotlin 项目 NPE 显著减少而非绝对为零。

> **Q：`lateinit` 和 `lazy` 区别？**
> `lateinit` 是 `var` 的「先声明后赋值」，只能非空非基本类型、不能在主构造、访问前未赋值会抛异常；适合依赖注入、生命周期回调注入。`lazy` 是 `val` 的延迟计算，首次访问触发、默认线程安全（双检锁）、记住结果；适合昂贵且可能不用的计算。

## 今日练习

1. 解释为什么 `val list = mutableListOf(1,2); list.add(3)` 合法，而 `list = mutableListOf()` 不合法。
2. 写一个安全的 `nick?.length ?: "无名".length`，并改成用 `if (nick != null)` 的等价写法，体会编译器的 smart cast。
3. 设计一个场景：用 `lateinit` 持有 Activity 里 `onCreate` 才创建的 View，并说明在 `onCreate` 前访问会怎样、怎么防御。
4. 写一个 `val cachedConfig by lazy(LazyThreadSafetyMode.NONE) { load() }`，说明它适合什么场景。

## 下一节预告

Day 2：`data class`、`sealed class/interface`、`object`——Kotlin 如何用三个关键字替代 Java 几十行样板代码，以及 `sealed` 给 `when` 带来的编译期穷尽检查。

---

## 摘要（200 字以内）

Day 1 建立 Kotlin 的两个安全基石：`val/var` 控制引用可变性（`val` 引用不可变但对象可变），`?` 区分非空与可空类型。空安全以编译期类型系统为主（非空不能赋 null、可空必须显式处理），运行时由编译器插入的实际检查包括 `Intrinsics` 非空参数断言和 `?.`/`!!` 的空值分支；可空性注解只是给互操作和工具传递的信息契约，本身不做拦截。纯 Kotlin 项目 NPE 显著减少而非「绝对为零」。延迟初始化分两套：`lateinit var` 适合依赖注入（仅非空非基本类型，不能在主构造），`val by lazy` 适合首次访问才计算（默认线程安全，可切 NONE）。

## 标签

#Kotlin #空安全 #Android面试 #val与var #延迟初始化
