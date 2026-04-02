package com.peknight.app

import com.peknight.build.gav
import fs2.io.file.Path
import org.http4s.Uri
import org.http4s.syntax.literals.uri

import java.net.URLEncoder
import java.nio.charset.StandardCharsets

package object build:
  object sbt:
    // https://github.com/sbt/sbt/releases
    val version: String = gav.sbtScala.version
    val url: Uri = Uri.unsafeFromString(s"https://github.com/sbt/sbt/releases/download/v$version/sbt-$version.tgz")
  end sbt
  object node:
    object linux:
      object x64:
        // https://nodejs.org/en/download/current
        val version: String = "25.8.2"
        val directory: Path = Path(s"node-v$version-linux-x64")
        val url: Uri = Uri.unsafeFromString(s"https://nodejs.org/dist/v$version/$directory.tar.xz")
      end x64
    end linux
  end node
  object fatedier:
    object frp:
      // https://github.com/fatedier/frp/releases/
      val version: String = "0.68.0"
      val url: Uri = Uri.unsafeFromString(s"https://github.com/fatedier/frp/releases/download/v$version/frp_${version}_linux_amd64.tar.gz")
    end frp
  end fatedier
  object adoptium:
    object temurin:
      // https://github.com/adoptium/temurin26-binaries/releases/
      object jdk:
        object x64:
          object linux:
            val version: String = "26_35"
            val url: Uri = Uri.unsafeFromString(s"https://github.com/adoptium/temurin26-binaries/releases/download/jdk-${URLEncoder.encode(version.replace('_', '+'), StandardCharsets.UTF_8)}/OpenJDK26U-jdk_x64_linux_hotspot_$version.tar.gz")
          end linux
        end x64
      end jdk
    end temurin
  end adoptium
  object xuxueli:
    object `xxl-job`:
      // https://github.com/xuxueli/xxl-job/releases/
      val version: String = "3.3.2"
      val tablesXxlJobSql: Uri = Uri.unsafeFromString(s"https://raw.githubusercontent.com/xuxueli/xxl-job/refs/tags/$version/doc/db/tables_xxl_job.sql")
    end `xxl-job`
  end xuxueli
  object mojang:
    object minecraft:
      object java:
        // https://www.minecraft.net/en-us/download/server
        val version: String = "26.1.1"
        val url: Uri = uri"https://piston-data.mojang.com/v1/objects/49c8195703ad0ba4f0a4efbccfd85a4a8ca57431/server.jar"
      end java
      object bedrock:
        // https://www.minecraft.net/en-us/download/server/bedrock
        val version: String = "1.26.12.2"
        val url: Uri = Uri.unsafeFromString(s"https://www.minecraft.net/bedrockdedicatedserver/bin-linux/bedrock-server-$version.zip")
      end bedrock
    end minecraft
  end mojang
end build
