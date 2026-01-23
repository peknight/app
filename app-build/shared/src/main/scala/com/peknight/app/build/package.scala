package com.peknight.app

import org.http4s.Uri

package object build:
  object fatedier:
    object frp:
      // https://github.com/fatedier/frp/releases/
      val version: String = "0.66.0"
      val url: Uri = Uri.unsafeFromString(s"https://github.com/fatedier/frp/releases/download/v$version/frp_${version}_linux_amd64.tar.gz")
    end frp
  end fatedier
end build
