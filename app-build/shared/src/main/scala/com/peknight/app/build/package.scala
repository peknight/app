package com.peknight.app

import org.http4s.Uri

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
end build
