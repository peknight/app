import com.peknight.build.gav.*
import com.peknight.build.sbt.*

commonSettings

lazy val app = (project in file("."))
  .settings(name := "app")
  .aggregate(
    appCore.jvm,
    appCore.js,
    appCore.native,
  )

lazy val appCore = (crossProject(JVMPlatform, JSPlatform, NativePlatform) in file("app-core"))
  .settings(name := "app-core")
