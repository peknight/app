package com.peknight.app

import cats.Applicative
import cats.syntax.eq.*
import com.peknight.codec.Codec
import com.peknight.codec.cursor.Cursor
import com.peknight.codec.sum.StringType

enum Environment(val slug: String):
  case Production extends Environment("prod")
  case Staging extends Environment("staging")
  case Testing extends Environment("test")
  case Development extends Environment("dev")
end Environment
object Environment:
  given stringCodecEnvironment[F[_]: Applicative]: Codec[F, String, String, Environment] =
    Codec.mapOption[F, String, String, Environment](_.toString)(t =>
      Environment.values.find(e => e.toString === t || e.slug === t)
    )
  given codecEnvironmentS[F[_]: Applicative, S: StringType]: Codec[F, S, Cursor[S], Environment] =
    Codec.codecS[F, S, Environment]
end Environment
