import com.peknight.build.gav.*
import com.peknight.build.sbt.*

commonSettings

lazy val app = (project in file("."))
  .settings(name := "app")
  .aggregate(
    appCore.jvm,
    appCore.js,
    appCore.native,
    appBuild.jvm,
    appBuild.js,
  )

lazy val appCore = (crossProject(JVMPlatform, JSPlatform, NativePlatform) in file("app-core"))
  .settings(name := "app-core")

lazy val appBuild = (crossProject(JVMPlatform, JSPlatform) in file("app-build"))
  .settings(name := "app-build")
  .settings(crossDependencies(http4s))
