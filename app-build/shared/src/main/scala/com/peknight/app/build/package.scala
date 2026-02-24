package com.peknight.app

import org.http4s.Uri
import org.http4s.syntax.literals.uri

import java.net.URLEncoder
import java.nio.charset.StandardCharsets

package object build:
  object fatedier:
    object frp:
      // https://github.com/fatedier/frp/releases/
      val version: String = "0.67.0"
      val url: Uri = Uri.unsafeFromString(s"https://github.com/fatedier/frp/releases/download/v$version/frp_${version}_linux_amd64.tar.gz")
    end frp
  end fatedier
  object adoptium:
    object temurin:
      // https://github.com/adoptium/temurin25-binaries/releases/
      object jdk:
        object x64:
          object linux:
            val version: String = "25.0.2_10"
            val url: Uri = Uri.unsafeFromString(s"https://github.com/adoptium/temurin25-binaries/releases/download/jdk-${URLEncoder.encode(version.replace('_', '+'), StandardCharsets.UTF_8)}/OpenJDK25U-jdk_x64_linux_hotspot_$version.tar.gz")
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
        val version: String = "1.21.11"
        val url: Uri = uri"https://piston-data.mojang.com/v1/objects/64bb6d763bed0a9f1d632ec347938594144943ed/server.jar"
      end java
      object bedrock:
        // https://www.minecraft.net/en-us/download/server/bedrock
        val version: String = "1.26.1.1"
        val url: Uri = Uri.unsafeFromString(s"https://www.minecraft.net/bedrockdedicatedserver/bin-linux/bedrock-server-$version.zip")
      end bedrock
    end minecraft
  end mojang
end build
