package com.peknight.app

import com.peknight.build.gav
import fs2.io.file.Path
import org.http4s.Uri
import org.http4s.syntax.literals.uri

import java.net.URLEncoder
import java.nio.charset.StandardCharsets

package object build:
  object adoptium:
    object temurin:
      /** @versionCheck https://api.adoptium.net/v3/info/available_releases */
      object jdk:
        object x64:
          object linux:
            val version: String = "26.0.2_10"
            val url: Uri = Uri.unsafeFromString(s"https://github.com/adoptium/temurin26-binaries/releases/download/jdk-${URLEncoder.encode(version.replace('_', '+'), StandardCharsets.UTF_8)}/OpenJDK26U-jdk_x64_linux_hotspot_$version.tar.gz")
          end linux
        end x64
      end jdk
    end temurin
  end adoptium
  object sbt:
    /** @skipVersionCheck https://repo.maven.apache.org/maven2/org/scala-sbt/sbt/ (version from build module) */
    val version: String = gav.sbtScala.version
    val url: Uri = Uri.unsafeFromString(s"https://github.com/sbt/sbt/releases/download/v$version/sbt-$version.tgz")
  end sbt
  object node:
    /** @versionCheck https://nodejs.org/dist/index.json */
    object linux:
      object x64:
        val version: String = "26.7.0"
        val directory: Path = Path(s"node-v$version-linux-x64")
        val url: Uri = Uri.unsafeFromString(s"https://nodejs.org/dist/v$version/$directory.tar.xz")
      end x64
    end linux
  end node
  object fatedier:
    /** @versionCheck https://api.github.com/repos/fatedier/frp/releases/latest */
    object frp:
      val version: String = "0.71.0"
      val url: Uri = Uri.unsafeFromString(s"https://github.com/fatedier/frp/releases/download/v$version/frp_${version}_linux_amd64.tar.gz")
    end frp
  end fatedier
  object xuxueli:
    /** @versionCheck https://api.github.com/repos/xuxueli/xxl-job/releases/latest */
    object `xxl-job`:
      val version: String = "3.4.2"
      val tablesXxlJobSql: Uri = Uri.unsafeFromString(s"https://raw.githubusercontent.com/xuxueli/xxl-job/refs/tags/$version/doc/db/tables_xxl_job.sql")
    end `xxl-job`
  end xuxueli
  object apolloconfig:
    /** @versionCheck https://api.github.com/repos/apolloconfig/apollo/releases/latest */
    object apollo:
      val version: String = "2.5.2"
      val apolloPortalDbSql: Uri = Uri.unsafeFromString(s"https://raw.githubusercontent.com/apolloconfig/apollo/refs/tags/v$version/scripts/sql/profiles/mysql-default/apolloportaldb.sql")
      val apolloConfigDbSql: Uri = Uri.unsafeFromString(s"https://raw.githubusercontent.com/apolloconfig/apollo/refs/tags/v$version/scripts/sql/profiles/mysql-default/apolloconfigdb.sql")
    end apollo
  end apolloconfig
  object mojang:
    object minecraft:
      /** @versionCheck https://launchermeta.mojang.com/mc/game/version_manifest.json */
      object java:
        val version: String = "26.2"
        val url: Uri = uri"https://piston-data.mojang.com/v1/objects/823e2250d24b3ddac457a60c92a6a941943fcd6a/server.jar"
      end java
      /** @versionCheck https://raw.githubusercontent.com/kittizz/bedrock-server-downloads/main/bedrock-server-downloads.json */
      object bedrock:
        val version: String = "1.26.44.3"
        val url: Uri = Uri.unsafeFromString(s"https://www.minecraft.net/bedrockdedicatedserver/bin-linux/bedrock-server-$version.zip")
      end bedrock
    end minecraft
  end mojang
end build
