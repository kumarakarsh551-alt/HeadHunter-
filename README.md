# HeadHunter (EX) boss – Forge 1.19.2 → 1.20.1 port kit

**Status: partial port, NOT compiled.** The environment this was prepared in had no network, no Forge/GeckoLib
jars and no Minecraft mappings, so nothing here has been built or run. What is finished, what is mechanical,
and what is still manual is listed below so you know exactly where you stand.

## What the source looks like
* 212 classes, ~1.7 MB, generated with MCreator: the boss's brain is ~100 `*Procedure` classes
  (`SwordDanceProProcedure` alone is 100 KB); the entity classes are thin shells that call them.
* The decompiled sources use **SRG names** (`m_6469_`, `f_19853_`; 455 distinct ids) because Forge reobfuscates
  released mods. They cannot compile against 1.20.1 until renamed.
* GeckoLib **3** is used by 20 files (6 animated entities + models/renderers/layer). 1.20.1 needs GeckoLib **4**
  (different packages and animation API), so those files need real rewrites, not renames.
* `Counterattack` and `VerticalBeamTickPro` were flagged by CFR ("Unable to fully structure code",
  see `legacy-1.19.2-src/summary.txt`); they may contain mangled control flow – re-decompile or review these two by hand.

## Done
| Item | Where |
|---|---|
| Forge 47 / ForgeGradle 6 / official-mappings build, GeckoLib 4 dependency | `build.gradle`, `gradle.properties`, `settings.gradle` |
| `mods.toml` (loader 47, MC 1.20.1, GeckoLib now **mandatory** – it was marked optional but the code hard-requires it), `pack_format` 15 | `src/main/resources` |
| All assets/data copied unchanged (geo `1.12.0` and animation `1.8.0` JSON load fine in GeckoLib 4; sounds, particles, textures, lang, recipes, advancements) | `src/main/resources` |
| **Boss entity** `HeadHunterEntity` → GeckoLib 4 + 1.20.1 API (`GeoEntity`, `RawAnimation`, `level()`, `DamageTypes`, `ClientGamePacketListener` spawn packet, …) | `entity/HeadHunterEntity.java` |
| Boss model + renderer (GeckoLib 4) | `entity/model/HeadHunterModel.java`, `client/renderer/HeadHunterRenderer.java` |
| Animation sync (pattern-matching rewrite of the CFR output) | `init/EntityAnimationFactory.java` |
| Damage: 1.20 removed `new DamageSource("x")`/`EntityDamageSource`. `HHDamage.of(...)` + 8 data-pack damage types reproduce them (same ids, no armor bypass, no difficulty scaling) | `HHDamage.java`, `data/headhunter_mod/damage_type/` |
| `srg2mojmap.py` – exact SRG→Mojang renamer (join of Mojang mappings + MCPConfig `joined.tsrg`, overloads resolved by descriptor; tested on a fixture) | `tools/` |
| `api_migrate_1_20.py` – safe 1.20 rewrites + TODO report (damage ctors/constants/tags, `new BlockPos(x,y,z)`→`BlockPos.containing`, `new SoundEvent`→`createVariableRangeEvent`, `.level`→`.level()`; dry-run on the real sources hit 115 damage constructors, 27 files with BlockPos, 51 SoundEvents) | `tools/` |
| **Other 5 GeckoLib entities** `HeadHunterDoubleBodyEntity`, `HHDeathEntityEntity`, `HHSpawnEntityEntity`, `ShadowGrabHandEntity`, `VerticalBeamEntity` → GeckoLib 4 / 1.20.1 (per-entity quirks kept: flying move control + navigation, no-gravity/no-push overrides, hurt-immunity list, attributes, controller transitions, death-tick counts, spawn/tick procedures) | `entity/*Entity.java` |
| Their 5 models + 5 renderers (VerticalBeam: scale 4 via `withScale(4f)`, replaces the `stack.scale` in `getRenderType`) | `entity/model/`, `client/renderer/` |
| `VerticalBeamLayer` → `GeoRenderLayer` + `reRender` | `entity/layer/VerticalBeamLayer.java` |
| Main class: `GeckoLib.initialize()` removed | `HeadhunterModMod.java` |
| `legacy-1.19.2-src/` – your decompiled sources, untouched, as the pipeline input | |

## To run the mechanical part (needs internet once)
1. Download the 1.19.2 Mojang mappings (`client_mappings` URL in the 1.19.2 version JSON → `client.txt`).
2. Get `config/joined.tsrg` from the MCPConfig 1.19.2 zip
   (`https://maven.minecraftforge.net/de/oceanlabs/mcp/mcp_config/1.19.2-20220805.130853/mcp_config-1.19.2-20220805.130853.zip`).
3. `tools/port.sh client.txt joined.tsrg` – renames, migrates, and copies into `src/main/java` without overwriting the hand-ported files.
4. `unmapped_ids.txt` should be empty (it lists ids that matched nothing); `MIGRATION_TODO.txt` lists the rest by file:line.
5. `./gradlew build`.

## Still manual (the real remaining work)
1. ~~GeckoLib 3 -> 4 entities~~ **done (see above), but uncompiled** - see "Assumptions to verify".
2. **Client rendering**: 5 `client/model/Model*` classes (Vector3f/Quaternion → JOML), `ColourScreenoverlayOverlay` (→ `GuiGraphics`),
   four mob-effect classes with inventory/HUD rendering (→ `IClientMobEffectExtensions` with `GuiGraphics`),
   `HHSpawnEntityRenderer` (PoseStack use).
3. **Items/spawn eggs/creative tab**: `.tab(CreativeModeTab…)` is gone; register a tab + `BuildCreativeModeTabContentsEvent`; spawn eggs → `ForgeSpawnEggItem`.
4. Review hits in `MIGRATION_TODO.txt` that the script only reports (explosions, single-argument `BlockPos`, remaining `DamageSource.X`).
5. **Playtest** – 1.20 also changed some mechanics subtly (e.g. damage-type tags such as `bypasses_armor`, projectile/explosion
   predicates). The boss has many timing-sensitive moves, so test every attack and difficulty item.

## Version notes to verify
`forge_version=47.3.0` and `geckolib_version=4.4.9` are my best pins for 1.20.1; if Gradle can't resolve them,
pick the nearest 47.x / 4.4.x release. Mod id stays `headhunter_mod` so existing assets and worlds keep matching.

## Assumptions to verify when you first compile (hand-ported entities)
I had no mappings offline, so these SRG -> Mojang translations in the 5 new entities came from memory:
* `DamageSource.f_19315_/f_19314_/f_19312_/f_19306_/f_19321_/f_19323_/f_19320_` -> `FALL/CACTUS/DROWN/LIGHTNING_BOLT/FALLING_ANVIL/DRAGON_BREATH/WITHER`;
  `m_19372_()` -> `isExplosion` (now `DamageTypeTags.IS_EXPLOSION`); `m_19385_()` msg ids `"trident"`/`"witherSkull"` -> `DamageTypes.TRIDENT/WITHER_SKULL`.
* Attribute ids `f_22278_` = `KNOCKBACK_RESISTANCE`, `f_22280_` = `FLYING_SPEED` (the first is confirmed by the boss's 0.7 value).
* `RenderType.m_110473_` = `entityTranslucent` (same choice as the boss renderer); the glow layer's `m_110488_` was taken to be `RenderType.eyes`.
Run `tools/port.sh` once: `unmapped_ids.txt`/a diff of `legacy-1.19.2-src` vs. the staged Mojang-named output will confirm or refute each line.
Also check: `withScale(4f)` exists in your GeckoLib 4.4.x (else override `scaleModelForRender`), and that the glow layer is scaled like the body.
Behaviour carried over unchanged: the `deathTime == 0` checks in DoubleBody/VerticalBeam are the original's (the counter is incremented first, so they never fire).
