# Selma Home 0.4.0 provenance

The canonical release input is the source in this directory. Generated DEX, APK,
keystore, password, and build directories are excluded from version control.

## Recovered inputs

| Input | SHA-256 | Use |
|---|---|---|
| `SelmaHome-0.4.0-source.zip` | `1a94feb7674b3cda3246730370ace421aacf8572f1dae1b8f323baadb1f92f4e` | Source baseline |
| `SelmaHome-0.4.0-preview.apk` | `ef1e25f2e470ce19d414aacd74617ae30d6978e21eb5d1adbfb0da1b352324db` | Preview integrity evidence only |

The preview APK is package `org.selma.home.preview`, version `0.4.0` (code 5),
min API 29, target API 35. Android `apksigner` verifies its APK Signature Scheme
v3 signature. The signer certificate SHA-256 is
`49b5349d261ded5b8ceb0935fe0be7fa5e7459575b6beba0262588cded786680`.

The preview APK's `classes.dex` is byte-identical to the reference DEX stored in
the recovered source ZIP. A current source rebuild produces a different DEX and
the recovered DEX contains two generated/inner classes absent from the current
source. The preview is therefore excluded as an official reproducible release.
Owner APKs must be rebuilt from the checked-in source and signed with the retained
owner key.

The bundled model is karpathy/tinyllamas `stories260K`. Its MIT license is stored
at `MODEL-LICENSE.txt` and embedded in APKs at
`assets/licenses/tinyllamas-MIT.txt`.

The model source payload is stored as two ordered files under `model/`. Both
builders concatenate those files into `assets/model.bin` and require the pinned
`b0a507e7ad0f626624f17112325e66691f9076d622e1d3274d103d00299f2696`
SHA-256 before packaging.
