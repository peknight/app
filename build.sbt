import com.peknight.build.gav.*
import com.peknight.build.sbt.*

commonSettings

lazy val app = (project in file("."))
  .settings(name := "app")
  .aggregate(appCore.projectRefs *)
  .aggregate(appBuild.projectRefs *)

lazy val appCore = (projectMatrix in file("app-core"))
  .settings(name := "app-core")
  .settings(libraryDependencies ++= dependencies(
    peknight.codec,
  ))
  .jvmPlatform(scalaVersions = Seq(scala.scala3.version))
  .jsPlatform(scalaVersions = Seq(scala.scala3.version))

lazy val appBuild = (projectMatrix in file("app-build"))
  .settings(name := "app-build")
  .settings(libraryDependencies ++= dependencies(
    http4s,
    peknight.build.gav,
  ))
  .jvmPlatform(scalaVersions = Seq(scala.scala3.version))
  .jsPlatform(scalaVersions = Seq(scala.scala3.version))
