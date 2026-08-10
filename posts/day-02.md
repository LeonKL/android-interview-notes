---
title: Android 面试学习 Day 2｜data class、sealed class/interface、object
tags: [Android, Kotlin, 面试, 知识星球]
created: 2026-07-28
updated: 2026-08-10
sources:
  - https://kotlinlang.org/docs/data-classes.html
  - https://kotlinlang.org/docs/sealed-classes.html
  - https://kotlinlang.org/docs/object-declarations.html
day: 2
---

# Android 面试学习 Day 2｜data class、sealed class/interface、object

> 导语：Java 写一个数据类要几十行（getter/setter/equals/hashCode/toString/copy），Kotlin 一个 `data class` 搞定；`sealed` 让 `when` 编译期穷尽；`object` 是单例。今天讲这三件 Kotlin 消灭样板代码的关键字。

## 今天学到了什么

1. `data class` 自动生成 `equals/hashCode/toString/copy/componentN`，基于**主构造属性**。
2. `sealed class/interface` 限制子类范围，让 `when` 编译期穷尽检查——状态机/UI 状态的基石。
3. `object` 是单例声明，`companion object` 是类级静态成员，二者初始化时机不同。

## 直观解释

**画面一：data class 是「填好表格的数据盒子」**

```kotlin
data class User(val name: String, val age: Int)
```

这一行等价于 Java 里：构造器 + 两个 getter + equals + hashCode + toString + copy + 两个 componentN（解构）。盒子里的「内容」就是主构造函数里那几个属性。

**画面二：sealed 是「清单上只有这几项的状态」**

```kotlin
sealed interface UiState {
    data object Loading : UiState
    data class Success(val data: String) : UiState
    data class Error(val msg: String) : UiState
}

fun render(state: UiState) = when (state) {
    is UiState.Loading -> showLoading()
    is UiState.Success -> showData(state.data)
    is UiState.Error  -> showError(state.msg)
    // 不用 else！新增一个状态编译器会强制你补上这里
}
```

清单是封闭的——编译器知道全部可能，所以 `when` 漏一个分支直接编译失败。这是比 `if-else` 强得多的安全保证。封闭范围是「同一 module 且同一 package」（多平台下还要同一 source set），不是「任何地方都能继承」。

**画面三：object 是「天生唯一的盒子」**

```kotlin
object AppConfig {
    var debug = false
    fun init() { /* ... */ }
}

// 用法：直接用名字
AppConfig.init()
```

`object` 声明的瞬间，它就是「整个程序里唯一一个实例」，你不用也不能 `new` 它。这就是单例模式。

## 核心原理

### data class 的规则

- **必须有主构造函数，至少一个参数**。
- 自动生成的方法**只基于主构造属性**——类体里单独声明的 `var` **不参与** equals/hashCode。
- 参数必须用 `val`/`var`（不能裸参数）。
- 自动生成的 `equals` 比较主构造属性；`copy` 允许按名修改部分字段；`component1()`/`component2()` 支持解构声明 `val (name, age) = user`。
- **data class 本身不能被继承**：官方原话「Data classes can't be abstract, open, sealed, or inner」。所以它不能加 `open`，别的类也无法继承一个 data class。
- **但 data class 可以继承其他类**（自 Kotlin 1.1 起）：例如 `data class User(val name: String) : Person()`，常见用法是让 data class 继承一个 sealed class 作为它的子类。

### sealed 的作用域规则（重要，易错）

按 Kotlin 官方文档，sealed 的子类位置受三层约束（不是单一「同 package」）：

1. **同一 module 且同一 package**（摘要原话：「No other subclasses may appear outside the **module and package** within which the sealed class is defined」）。继承规则正文进一步强调「**Direct subclasses must be declared in the same package**」，可顶层或嵌套在任意命名类/接口/object 中。
2. **必须有全限定名**——不能是 local 类或匿名对象。
3. **多平台项目额外约束**：直接子类必须在「同一 source set」（除非用 expect/actual 声明）。

> 历史演变提醒：旧版本 Kotlin 曾是「同一文件」，后来放宽。现版本是「同 module + 同 package（多平台再加同 source set）」。回答面试时讲当前规则即可，可补充「这个范围历史上放宽过」体现深度，但不要简化成「只看 package」。

`when` 用在 sealed 上，编译器做**穷尽性检查（exhaustive）**：覆盖所有子类就不需要 `else`；以后加新子类，所有 `when` 都会编译失败，强迫你补全——这就是「封闭类型」的核心价值。

### object 的三种形态与初始化时机

官方明确区分三者：

- **object declaration**（`object Foo {}`）：单例。**懒初始化，首次访问时初始化，线程安全**。不能是局部的。
- **companion object**：类内部用 `companion` 声明，提供类级成员（类似 Java 静态）。**在类被加载（解析）时初始化**，语义等同 Java 静态初始化器。
- **object expression**（`val x = object {}`）：匿名对象，**立即初始化**，用在哪里就在哪里实例化。

初始化时机的差异（直接来自官方）：
> - object 表达式：立即初始化。
> - object 声明：首次访问时懒初始化。
> - companion object：对应类加载时初始化。

`INSTANCE` 是 JVM 互操作产物：`object Foo` 在字节码层面是「一个类 `Foo` + 一个 `public static final INSTANCE` 字段」，Java 调用要 `Foo.INSTANCE.bar()`。这是实现细节，不是 Kotlin 语法。

## Kotlin/Android 示例

```kotlin
// 1. data class 作 DTO
data class Article(val id: Long, val title: String, val tags: List<String>)

val a = Article(1, "Kotlin", listOf("lang"))
val b = a.copy(title = "Kotlin 基础")   // copy 改部分字段
val (id, title, _) = a                  // 解构声明

// 2. sealed 表达 UI 状态（Android 最典型用法）
sealed interface LoginState {
    data object Idle : LoginState
    data object Loading : LoginState
    data class Success(val token: String) : LoginState
    data class Failed(val code: Int) : LoginState
}

class LoginViewModel : ViewModel() {
    private val _state = MutableStateFlow<LoginState>(LoginState.Idle)
    val state = _state.asStateFlow()
}

// 3. object 单例 + companion 工厂
object Logger {
    fun d(msg: String) { /* ... */ }
}

class User private constructor(val id: String) {
    companion object {
        fun create(id: String) = User(id)
    }
}
```

## 常见误区

1. **「data class 的 equals 基于所有字段」**：错，只基于主构造属性。类体里的 `var` 不参与，会出现「看着一样但 equals 返回 false」。
2. **「sealed 子类必须在同一文件」**：现版本是「同一 module 且同一 package」（多平台下还要同一 source set），不是「同一文件」，也不是「只看 package」。这是版本演进坑。
3. **「object 在类加载时就初始化」**：错。object **声明**是首次**访问**时懒初始化；只有 **companion object** 是类加载时初始化。两者别混。
4. **「object 可以放在函数里」**：object **声明**不能是局部的；局部只能用 object **表达式**（匿名对象）。
5. **「data class 加 open 就能被继承」**：错。官方原话「Data classes can't be abstract, open, sealed, or inner」——data class **根本不能被继承**，加 `open` 直接编译错误。但 data class **可以继承其他类**（自 Kotlin 1.1 起），常见用法是让 data class 作为 sealed class 的子类。

## 面试回答

> **Q：data class 和普通 class 区别？**
> data class 是为「数据载体」设计的，自动生成 equals/hashCode/toString/copy/componentN，**基于主构造属性**。典型场景 DTO、领域模型。坑：类体内单独声明的字段不参与 equals；data class 不能被继承（不能加 abstract/open/sealed/inner），但可以继承其他类（自 Kotlin 1.1 起，常作为 sealed class 的子类）。

> **Q：sealed class 和 abstract class 区别？**
> sealed 限制直接子类必须在同一 module 且同一 package（多平台下还要同一 source set），编译器知道全部子类，所以 `when` 能编译期穷尽检查，新增子类时所有 when 强制补全。abstract 没有这个范围限制，when 需要 else。sealed 是状态机、Result 类型、UiState 的首选。

> **Q：data class 能被继承吗？能继承别的类吗？**
> 不能被继承：官方规定 data class 不能加 abstract/open/sealed/inner，所以别的类无法继承一个 data class。但 data class 自身可以继承其他类（Kotlin 1.1 起），典型用法是让 data class 作为 sealed class 的子类。注意自动生成的 equals/hashCode 只基于主构造属性。

## 今日练习

1. 定义一个 `data class Point(val x: Int, val y: Int)`，验证 `Point(1,2) == Point(1,2)` 为 true，并尝试解构 `val (x, y) = point`。
2. 把一个 `if-else` 处理的网络回调（success/failure）改写成 sealed 表达，并写 `when` 分发，体验「新增分支编译报错」的好处。
3. 写一个 `object EventBus` 单例，再写一个带 `companion object` 的 `User` 类提供 `create()` 工厂，说明两者初始化时机区别。
4. 故意在 data class 类体里加一个 `var extra = 0`，验证它不参与 equals。

## 下一节预告

Day 3：扩展函数、委托（by）、高阶函数——在不改类源码的前提下给它加方法，把「样板代码」交给委托，把函数当参数传。

---

## 摘要（200 字以内）

Day 2 学三个 Kotlin 消除样板代码的关键字。`data class` 一行替代 Java 几十行，自动生成 equals/hashCode/toString/copy/componentN，只基于主构造属性（类体字段不参与）；它本身不能被继承（官方规定不能加 abstract/open/sealed/inner），但可以继承其他类（如作为 sealed 子类）。`sealed class/interface` 把直接子类限定在同一 module 且同一 package（多平台还要同 source set），让 `when` 编译期穷尽检查，是状态机和 UiState 的基石（作用域历史上从 file 放宽，但仍是 module+package 双重约束，不是只看 package）。`object` 是懒初始化单例，`companion object` 是类加载时初始化的类级成员载体，初始化时机不同别混。

## 标签

#Kotlin #dataClass #sealed #object #Android面试
