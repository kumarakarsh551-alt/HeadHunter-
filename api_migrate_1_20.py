#!/usr/bin/env python3
"""
api_migrate_1_20.py - second pass, run AFTER srg2mojmap.py.

Applies the mechanical 1.19.2 -> 1.20.1 API rewrites that are safe to automate and writes
MIGRATION_TODO.txt listing every spot that needs a human (or a follow-up pass) with file:line.

Automated rewrites
  * new DamageSource("x") / new EntityDamageSource("x", e) -> HHDamage.of("x") / HHDamage.of("x", e)
    (1.20 damage types are data-driven; HHDamage + data/headhunter_mod/damage_type/*.json provide them)
  * source == DamageSource.FALL / .equals(...)       -> source.is(DamageTypes.FALL)
  * source.isExplosion() / isProjectile() / isFire() -> source.is(DamageTypeTags.IS_...)
  * new BlockPos(x, y, z)                            -> BlockPos.containing(x, y, z)
  * new SoundEvent(rl)                               -> SoundEvent.createVariableRangeEvent(rl)
  * expr.level (field)                               -> expr.level()
  * adds missing imports for the above
Everything else it only reports.

Usage: python api_migrate_1_20.py SRC_DIR            (edits in place; keep a backup/VCS!)
"""
import os, re, sys


DAMAGE_CONST = {
    "IN_FIRE": "IN_FIRE", "LIGHTNING_BOLT": "LIGHTNING_BOLT", "ON_FIRE": "ON_FIRE", "LAVA": "LAVA",
    "HOT_FLOOR": "HOT_FLOOR", "IN_WALL": "IN_WALL", "CRAMMING": "CRAMMING", "DROWN": "DROWN",
    "STARVE": "STARVE", "CACTUS": "CACTUS", "FALL": "FALL", "FLY_INTO_WALL": "FLY_INTO_WALL",
    "GENERIC": "GENERIC", "MAGIC": "MAGIC", "WITHER": "WITHER", "ANVIL": "FALLING_ANVIL",
    "FALLING_BLOCK": "FALLING_BLOCK", "DRAGON_BREATH": "DRAGON_BREATH", "DRY_OUT": "DRY_OUT",
    "SWEET_BERRY_BUSH": "SWEET_BERRY_BUSH", "FREEZE": "FREEZE", "STALAGMITE": "STALAGMITE",
}
TAG_METHODS = {
    "isExplosion": "IS_EXPLOSION", "isProjectile": "IS_PROJECTILE", "isFire": "IS_FIRE",
    "isFall": "IS_FALL", "isBypassArmor": "BYPASSES_ARMOR", "isBypassInvul": "BYPASSES_INVULNERABILITY",
    "isBypassMagic": "BYPASSES_EFFECTS",
}

REPORT_PATTERNS = [
    (r"com\.mojang\.math\.(Vector3f|Quaternion|Matrix4f|Matrix3f)", "JOML migration: Vector3f/Quaternion -> org.joml + com.mojang.math.Axis"),
    (r"GuiComponent|RenderSystem|ForgeIngameGui|RenderGameOverlayEvent|IIngameOverlay", "GUI/overlay rewrite: use GuiGraphics + RenderGuiEvent / RegisterGuiOverlaysEvent"),
    (r"IClientMobEffectExtensions|renderInventoryEffect|renderHUDEffect|renderInventoryText", "Mob effect client rendering: signatures now take GuiGraphics"),
    (r"CreativeModeTab|\.tab\(", "Creative tabs: register via CreativeModeTab registry + BuildCreativeModeTabContentsEvent"),
    (r"DamageSource\.[A-Z_]+", "DamageSource constant remains"),
    (r"\.explode\(|Explosion\.BlockInteraction", "Explosions: use Level.ExplosionInteraction"),
    (r"new BlockPos\([^,()]*\)", "BlockPos single-argument constructor: check manually"),
    (r"SimpleChannel|NetworkRegistry", "Networking unchanged in Forge 47 - verify only"),
    (r"software\.bernie\.geckolib3", "GeckoLib 3 import remains: port to GeckoLib 4"),
    (r"\bm_\d+_\b|\bf_\d+_\b", "Unmapped SRG identifier remains"),
]


def balanced_args(s, i):
    """s[i] == '(' -> (index_after_close, top-level comma count) or None"""
    depth, commas, j, n = 0, 0, i, len(s)
    while j < n:
        c = s[j]
        if c == '"':
            j += 1
            while j < n and s[j] != '"':
                j += 2 if s[j] == '\\' else 1
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return j + 1, commas
        elif c == "," and depth == 1:
            commas += 1
        j += 1
    return None



def rewrite_ctor(text, cls, repl):
    """Rewrite `new cls(args)` -> repl(args_text); args are split at top level."""
    out, i, key = [], 0, f"new {cls}("
    while True:
        k = text.find(key, i)
        if k < 0:
            out.append(text[i:])
            break
        p = k + len(key) - 1
        res = balanced_args(text, p)
        out.append(text[i:k])
        if not res:
            out.append(key)
            i = k + len(key)
            continue
        end, _ = res
        out.append(repl(text[p + 1:end - 1]))
        i = end
    return "".join(out)

def rewrite_blockpos(text):
    out, i, key = [], 0, "new BlockPos("
    while True:
        k = text.find(key, i)
        if k < 0:
            out.append(text[i:])
            break
        p = k + len(key) - 1
        res = balanced_args(text, p)
        out.append(text[i:k])
        if res and res[1] == 2:
            end, _ = res
            out.append("BlockPos.containing(" + text[p + 1:end])
            i = end
        else:
            out.append(key)
            i = k + len(key)
    return "".join(out)


def add_import(text, fq):
    line = f"import {fq};"
    if line in text:
        return text
    m = re.search(r"^import .*;$", text, re.M)
    return text[:m.start()] + line + "\n" + text[m.start():] if m else re.sub(r"(package .*;\n)", r"\1\n" + line + "\n", text, 1)


def process(path, todo):
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    t = src
    # 1. data-driven damage types
    n1 = 0
    def _plain(args):
        nonlocal n1
        n1 += 1
        return f"HHDamage.of({args})"
    t = rewrite_ctor(t, "DamageSource", _plain)
    t = rewrite_ctor(t, "EntityDamageSource", _plain)
    t = rewrite_ctor(t, "IndirectEntityDamageSource", _plain)
    if n1:
        t = add_import(t, "net.shadow.headhuntermod.HHDamage")
    t = re.sub(r"^import net\.minecraft\.world\.damagesource\.(Entity|IndirectEntity)DamageSource;\n", "", t, flags=re.M)
    # 2. damage-type constants
    def const(m):
        name = DAMAGE_CONST.get(m.group(2))
        return f"{m.group(1)}.is(DamageTypes.{name})" if name else m.group(0)
    t, n2 = re.subn(r"(\w+) == DamageSource\.([A-Z_]+)", const, t)
    t, n3 = re.subn(r"(\w+)\.equals\(DamageSource\.([A-Z_]+)\)", const, t)
    if n2 or n3:
        t = add_import(t, "net.minecraft.world.damagesource.DamageTypes")
    # 3. predicate methods -> tags
    def tag(m):
        return f"{m.group(1)}.is(DamageTypeTags.{TAG_METHODS[m.group(2)]})"
    t, n4 = re.subn(r"(\w+)\.(" + "|".join(TAG_METHODS) + r")\(\)", tag, t)
    if n4:
        t = add_import(t, "net.minecraft.tags.DamageTypeTags")
    # 4. BlockPos / SoundEvent / level
    before = t
    t = rewrite_blockpos(t)
    n5 = t != before
    t, n6 = re.subn(r"new SoundEvent\(", "SoundEvent.createVariableRangeEvent(", t)
    lines, n7 = [], 0
    for ln in t.split("\n"):
        if not ln.lstrip().startswith(("import ", "package ")):
            new = re.sub(r"(?<![\w.])((?:this|[a-z]\w*))\.level\b(?!\s*[(\w])(?!\.(?:[a-z]+\.)*[A-Z])", r"\1.level()", ln)
            if new != ln:
                n7 += 1
            ln = new
        lines.append(ln)
    t = "\n".join(lines)
    changed = t != src
    if changed:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(t)
    # report
    for no, ln in enumerate(t.split("\n"), 1):
        if ln.lstrip().startswith(("import ", "package ", "*", "/*")):
            if not re.search(r"geckolib3|com\.mojang\.math|GuiComponent|RenderSystem", ln):
                continue
        for rx, msg in REPORT_PATTERNS:
            if re.search(rx, ln):
                todo.append(f"{path}:{no}: {msg}")
    return changed, (n1, n2 + n3, n4, n5, n6, n7)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    root, todo, stats = sys.argv[1], [], [0] * 6
    files = 0
    for d, _, fs in os.walk(root):
        for f in fs:
            if f.endswith(".java"):
                ch, s = process(os.path.join(d, f), todo)
                files += ch
                stats = [a + int(b) for a, b in zip(stats, s)]
    with open(os.path.join(root, "MIGRATION_TODO.txt"), "w") as fh:
        fh.write("\n".join(todo) + "\n")
    print(f"{files} files changed | hurt(DamageSource)={stats[0]} dmg-const={stats[1]} dmg-tag={stats[2]} "
          f"blockpos-files={stats[3]} soundevent={stats[4]} level-lines={stats[5]} | {len(todo)} TODO lines")


if __name__ == "__main__":
    main()
