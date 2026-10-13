#!/usr/bin/env python3
"""tables/bindings.tsv: the shape of every Lua binding the client registers: name, argument
count, return arity and return kinds.

A client that checks its Lua globals by name accepts a binding with the right name and the wrong
return arity, and that silently breaks a stock interface file, because `local a, b = F()` binds b
to whatever the engine did or did not push. A name says nothing about shape.

How the shape is read. A binding is a function `int __fastcall (lua_State *L)`: eax at its `ret`
is the number of values it returns. The generator recovers that by abstract interpretation over
the function's own control-flow graph, and cross-checks it against an independent signal, the
ordered lua_push* calls that reach the same `ret`. The Lua C API calls it models:

    pushers      lua_pushnil/number/string/lstring/vfstring/fstring/boolean/lightuserdata,
                 lua_pushvalue, lua_newtable, lua_rawgeti: net +1 on the Lua stack, one kind each
    lua_pushstring (0x6f3890) alone begins `test edx,edx; jne` and tail-jumps to lua_pushnil
                 for a NULL char*, so it yields kind `string?` (string or nil) unless edx is a
                 constant that points at a readable literal
    lua_settable/rawset/rawseti pop two/two/one, lua_settop(L, negative) pops -idx-1
    lua_gettable (0x6f3a40) and lua_rawget (0x6f3b00) pop the key and write the looked-up
                 value into that same slot: net zero, and the slot's kind becomes `any`
    every other call into the C API band that is not a known stack-inert reader makes the
                 trace unknown, never a guess; lua_error, luaL_error and the CRT longjmp do not
                 return

Registration routes, each extent read from the registrar's own literal (never a run scan):
0x704120 RegisterFunction loops (global); 0x701d80 RegisterMethods (widget method tables); the
base-library loop inlined around the lua_pushcclosure call sites; and the four luaL_openlib
0x6f4dc0 tables (bit, math, table, string).

Columns, and what may be relied on:
  arity, arity_conf   sound. exact is one constant; set is a `|`-separated set of possible
                      counts; unknown is `?`. The lattice only widens at a merge, so an
                      imprecise result is a set or `?`, never a wrong single number.
  kinds, kinds_conf   `agree` means the push trace's length set equals the eax set at every ret
                      and every ret was checked. Otherwise advisory: a loop saturates the trace
                      (GetTexCoord: 2 textual pushes, 8 real) and the row says `unverified`.
                      `agree` does not cover a callee that pushes for the binding: that is the
                      note `delegated-push`.
  argc, argc_conf     a floor, never a gate: the largest constant Lua stack index the binding
                      reads. A binding that hands its argument parsing to a helper is marked
                      `lower-bound`, and the detector is one call deep, so every argc is a floor.
  name                not a key. Sixty names are registered from more than one table, and some of
                      those differ in arity (GetBuildInfo returns 5 on the glue screen and 3
                      in-game). Key on fn, or on (table_va, name). Such rows carry
                      `name-not-unique`.
  notes               stack-leak: the binding pushes values and returns fewer; a faithful client
                      must not copy it. variadic: the count comes from lua_gettop.
                      delegated-push, name-not-unique, and the unsound-edge flags
                      cfg-truncated, indirect-branch and iteration-cap: an edge the walk could
                      not resolve, outside the soundness claim for that row's arity.

The disassembly restarts at every function row and jump-table entry (tools/disasm.sh), but data
no row or table accounts for can still knock it out of step. A branch target that it has inside
one instruction is disassembled afresh from that address with objdump (lib.Disasm.lookup);
without objdump the walk is truncated there and the row says `cfg-truncated`.
"""

import re
import struct
import sys

from lib import Disasm, Image, addr, note, parse_args, write_table

# ------------------------------------------------------------------ registrars and helpers
REG_FUNCTION = 0x704120      # RegisterFunction(ecx = name, edx = fn)
REG_METHODS = 0x701D80       # RegisterMethods(ecx = base, edx = count, [esp+4] = map)
LUA_PUSHCCLOSURE = 0x6F3920  # anchor for the inlined base-library loop
LUAL_OPENLIB = 0x6F4DC0      # the standard libraries, NULL-terminated tables

PUSHERS = {
    0x6f37f0: 'nil',            # lua_pushnil
    0x6f3810: 'number',         # lua_pushnumber
    0x6f3890: 'string',         # lua_pushstring, see PUSHSTRING
    0x6f3840: 'string',         # lua_pushlstring
    0x6f38c0: 'string',         # lua_pushvfstring
    0x6f38f0: 'string',         # lua_pushfstring
    0x6f39f0: 'boolean',        # lua_pushboolean
    0x6f3a20: 'lightuserdata',  # lua_pushlightuserdata
    0x6f3350: 'value',          # lua_pushvalue(idx)
    0x6f3c90: 'table',          # lua_newtable
    0x6f3bc0: 'any',            # lua_rawgeti(idx, n)
}
PUSHSTRING = 0x6f3890
SETTOP = 0x6f3080
POPS_N = {0x6f3e20: 2,         # lua_settable
          0x6f3ea0: 2,         # lua_rawset
          0x6f3f60: 1}         # lua_rawseti
GETTOP = 0x6f3070
REPLACE_TOP = {0x6f3a40: 'any',   # lua_gettable
               0x6f3b00: 'any'}   # lua_rawget
LAPI_LO, LAPI_HI = 0x6f3020, 0x6f4600
NEUTRAL_READERS = frozenset({
    0x6f3070, 0x6f3400, 0x6f3410, 0x6f34a0, 0x6f34d0, 0x6f3510, 0x6f3530, 0x6f3620,
    0x6f3660, 0x6f3690, 0x6f36e0, 0x6f3720, 0x6f3740, 0x6f3770, 0x6f3790,
    0x6f3480, 0x6f3550, 0x6f43c0, 0x6f43d0, 0x6f43e0, 0x6f43f0, 0x6f4400, 0x6f4370,
})
IDX_READERS = {                 # take the Lua stack index in edx
    0x6f3400: 'lua_type', 0x6f3510: 'lua_isstring', 0x6f34d0: 'lua_isnumber',
    0x6f3530: 'lua_isuserdata', 0x6f34a0: 'lua_iscfunction',
    0x6f3620: 'lua_tonumber', 0x6f3690: 'lua_tostring', 0x6f3660: 'lua_toboolean',
    0x6f3740: 'lua_touserdata', 0x6f36e0: 'lua_strlen', 0x6f3770: 'lua_tothread',
    0x6f3790: 'lua_topointer', 0x6f3720: 'lua_tocfunction', 0x6f3bc0: 'lua_rawgeti',
    0x6f3350: 'lua_pushvalue', 0x6f3a40: 'lua_gettable', 0x6f3b00: 'lua_rawget',
    0x6f3cf0: 'lua_getmetatable', 0x6f1c10: 'FrameScript_GetBoolOrDefault',
    0x6f4c80: 'luaL_checknumber', 0x6f4b50: 'luaL_check_a', 0x6f4be0: 'luaL_check_b',
    0x6f4bb0: 'luaL_check_c', 0x6f4cd0: 'luaL_check_d', 0x6f4c20: 'luaL_check_e',
}
# luaL_error, lua_error and the CRT longjmp never return. lua_error is listed because
# luaD_throw's `call [edx+0x2c]` panic slot is an indirect call the walk will not see through.
NORETURN_SEED = frozenset({0x6f4940, 0x6f4440, 0x742014})

REGS = ('eax', 'ecx', 'edx', 'ebx', 'esp', 'ebp', 'esi', 'edi')
PARENT = {r: r for r in REGS}
for _n, _p in (('ax', 'eax'), ('al', 'eax'), ('ah', 'eax'), ('cx', 'ecx'), ('cl', 'ecx'),
               ('ch', 'ecx'), ('dx', 'edx'), ('dl', 'edx'), ('dh', 'edx'), ('bx', 'ebx'),
               ('bl', 'ebx'), ('bh', 'ebx'), ('si', 'esi'), ('di', 'edi'),
               ('sp', 'esp'), ('bp', 'ebp'), ('sil', 'esi'), ('dil', 'edi')):
    PARENT[_n] = _p

VCAP, PCAP, LCAP, MAX_SPAN = 8, 6, 24, 0x8000
M32 = 0xFFFFFFFF

# ------------------------------------------------------------------ the image
IMG = None
DIS = None
TEXT_LO = TEXT_HI = RD_LO = RD_HI = DA_LO = DA_INIT_HI = 0


def setup(img, dis):
    global IMG, DIS, TEXT_LO, TEXT_HI, RD_LO, RD_HI, DA_LO, DA_INIT_HI
    IMG, DIS = img, dis
    TEXT_LO, TEXT_HI = img.sections['.text'][:2]
    RD_LO, RD_HI = img.sections['.rdata'][:2]
    DA_LO = img.sections['.data'][0]
    DA_INIT_HI = DA_LO + img.sections['.data'][2]


def u32(va):
    return IMG.u32(va)


def cstr(va, cap=64):
    if not (RD_LO <= va < RD_HI or DA_LO <= va < DA_INIT_HI):
        return None
    o = va - IMG.base
    e = IMG.mem.find(b'\x00', o, o + cap)
    if e < 0:
        return None
    s = bytes(IMG.mem[o:e])
    if not s or not all(32 <= c < 127 for c in s):
        return None
    return s.decode('ascii')


def is_ident(s):
    return bool(s) and 1 < len(s) < 64 and (s[0].isalpha() or s[0] == '_') \
        and all(c.isalnum() or c == '_' for c in s)


def is_code(va):
    return TEXT_LO <= va < TEXT_HI


def padded(va):
    return TEXT_LO < va < TEXT_HI and IMG.u8(va - 1) in (0x90, 0xCC)


# ------------------------------------------------------------------ instructions
class Ins:
    __slots__ = ('addr', 'size', 'mn', 'ops')


_MEMSIZE = re.compile(r'^(?:[A-Z]+ PTR )?(?:[a-z]s:)?')
_IMM = re.compile(r'^-?0x[0-9a-f]+$')


def parse_operand(s):
    """('imm', value) | ('reg', name) | ('mem', base, index, scale, disp) | ('other', text)."""
    s = s.strip()
    if _IMM.match(s):
        return ('imm', int(s, 16) & M32)
    if s in PARENT:
        return ('reg', s)
    t = re.sub(r'^[A-Z]+ PTR ', '', s)
    seg = re.match(r'^[a-z]s:', t)
    if seg:
        t = t[3:]
    if _IMM.match(t):
        return ('mem', None, None, 1, int(t, 16))
    m = re.fullmatch(r'\[(.*)\]', t)
    if not m:
        return ('other', s)
    base = index = None
    scale, disp = 1, 0
    for sign, term in re.findall(r'([+-]?)([^+-]+)', m.group(1)):
        neg = sign == '-'
        if term in PARENT:
            if base is None and not neg:
                base = term
            else:
                index = term
        elif '*' in term:
            r, k = term.split('*')
            index, scale = r, int(k, 0)
        elif _IMM.match(term) or term.startswith('0x'):
            v = int(term, 16)
            disp += -v if neg else v
        else:
            return ('other', s)
    return ('mem', base, index, scale, disp)


_cache = {}


def decode(va):
    """The instruction at va in the listing, or None if the listing has none there."""
    if va in _cache:
        return _cache[va]
    r = None
    t = DIS.lookup(va) if TEXT_LO <= va < TEXT_HI else None
    if t is not None:
        a, size, mn, ops = t
        if mn != '(bad)' and mn:
            r = Ins()
            r.addr, r.size, r.mn = a, size, mn
            r.ops = [parse_operand(o) for o in ops.split(',')] if ops else []
    _cache[va] = r
    return r


# ------------------------------------------------------------------ harvest
def callsites(target):
    return IMG.call_sites(target)


def tbytes(va, n):
    return IMG.bytes(va, n)


def rows_at(base, count):
    out = []
    for i in range(count):
        p = base + 8 * i
        out.append((p, cstr(u32(p)), u32(p + 4)))
    return out


def harvest():
    tables, unresolved = {}, []

    def add(base, kind, count, site, lib=None):
        if base in tables:
            tables[base]['sites'].append(site)
        else:
            tables[base] = dict(kind=kind, rows=rows_at(base, count), sites=[site], lib=lib)

    for site in callsites(REG_FUNCTION):                    # (a)
        pre, fw = tbytes(site - 6, 6), tbytes(site + 5, 12)
        if pre[0:2] != b'\x8b\x8e' or fw[0:3] != b'\x83\xc6\x08':
            unresolved.append((site, 'a'))
            continue
        base = struct.unpack_from('<I', pre, 2)[0]
        if fw[3:5] == b'\x81\xfe':
            limit = struct.unpack_from('<I', fw, 5)[0]
        elif fw[3:5] == b'\x83\xfe':
            limit = fw[5]
        else:
            unresolved.append((site, 'a'))
            continue
        add(base, 'global', limit // 8, site)

    for site in callsites(REG_METHODS):                     # (b)
        pre = tbytes(site - 20, 20)
        if pre[15] != 0xB9:
            unresolved.append((site, 'b'))
            continue
        base = struct.unpack_from('<I', pre, 16)[0]
        count = None
        for i in range(14, -1, -1):
            if pre[i] == 0xBA:
                count = struct.unpack_from('<I', pre, i + 1)[0]
                break
        if count is None or not 0 < count < 4096:
            unresolved.append((site, 'b'))
            continue
        add(base, 'widget', count, site)

    for site in callsites(LUA_PUSHCCLOSURE):                # (c) the inlined loop
        win = tbytes(site - 96, 96 + 64)
        disps = [struct.unpack_from('<I', win, i + 2)[0]
                 for i in range(len(win) - 6)
                 if win[i:i + 2] in (b'\x8b\x96', b'\x8b\x8e')]
        disps = [d for d in disps if is_ident(cstr(u32(d)) or '')]
        tail = win[96:]
        j = tail.find(b'\x83\xc6\x08')
        if not disps or j < 0:
            continue
        if tail[j + 3:j + 5] == b'\x81\xfe':
            limit = struct.unpack_from('<I', tail, j + 5)[0]
        elif tail[j + 3:j + 5] == b'\x83\xfe':
            limit = tail[j + 5]
        else:
            continue
        add(min(disps), 'baselib', limit // 8, site)

    for site in callsites(LUAL_OPENLIB):                    # (d)
        pre, base, lib = tbytes(site - 20, 20), None, None
        for i in range(len(pre) - 5, -1, -1):
            if pre[i] == 0x68:
                cand = struct.unpack_from('<I', pre, i + 1)[0]
                if is_ident(cstr(u32(cand)) or '') and is_code(u32(cand + 4)):
                    base = cand
                    break
        for i in range(len(pre) - 5, -1, -1):
            if pre[i] == 0xBA:
                lib = cstr(struct.unpack_from('<I', pre, i + 1)[0])
                break
        if base is None:
            unresolved.append((site, 'd'))
            continue
        n = 0
        while u32(base + 8 * n):
            n += 1
        add(base, 'stdlib', n, site, lib)

    return tables, unresolved


# ------------------------------------------------------------------ the control-flow graph
class Fn:
    __slots__ = ('entry', 'insns', 'succ', 'rets', 'calls', 'tails',
                 'indirect', 'switches', 'trunc')


_cfg = {}


def explore(entry):
    """Recursive-traversal CFG. Every unresolvable edge is counted, never dropped silently:
    `trunc` and `indirect` bound the soundness claim on arity."""
    if entry in _cfg:
        return _cfg[entry]
    f = Fn()
    f.entry, f.insns, f.succ, f.rets = entry, {}, {}, []
    f.calls, f.tails, f.indirect, f.switches, f.trunc = [], [], [], [], False
    _cfg[entry] = f
    work = [entry]
    while work:
        va = work.pop()
        if va in f.insns:
            continue
        if not (entry - 0x20 <= va < entry + MAX_SPAN):
            f.trunc = True
            continue
        ins = decode(va)
        if ins is None:
            f.trunc = True
            continue
        f.insns[va] = ins
        nxt, m, s = va + ins.size, ins.mn, []
        if m in ('ret', 'retf', 'iret'):
            f.rets.append(va)
        elif m == 'jmp':
            op = ins.ops[0]
            if op[0] == 'imm':
                t = op[1]
                if entry <= t < entry + MAX_SPAN and not (padded(t) and t != entry):
                    s = [t]
                else:
                    f.tails.append((va, t))
            elif op[0] == 'mem' and op[2] is not None and op[3] == 4 and op[1] is None:
                tbl = op[4] & M32
                f.switches.append(tbl)
                for i in range(600):
                    e = tbl + 4 * i
                    if not (TEXT_LO <= e < TEXT_HI - 4):
                        break
                    t = u32(e)
                    if not (entry <= t < entry + MAX_SPAN):
                        break
                    s.append(t)
            else:
                f.indirect.append(va)
        elif m.startswith('j'):
            op = ins.ops[0]
            if op[0] == 'imm':
                s = [op[1], nxt]
            else:
                f.indirect.append(va)
                s = [nxt]
        elif m == 'call':
            op = ins.ops[0]
            f.calls.append((va, op[1] if op[0] == 'imm' else None))
            s = [nxt]
        elif m in ('int3', 'ud2', 'hlt'):
            pass
        else:
            s = [nxt]
        f.succ[va] = s
        work.extend(s)
    return f


_noret = {}


def is_noreturn(fva, seed, depth=0):
    """No `ret` is reachable once `seed` is honoured. A tail jmp counts as returning unless its
    own target is noreturn. Anything the walk cannot see (truncation, an indirect jump,
    recursion past the bound) is assumed to return, so the model can only keep a `ret`, never
    invent one."""
    if fva in seed:
        return True
    if depth > 6:
        return False
    key = (fva, depth)
    if key in _noret:
        return _noret[key]
    _noret[key] = False                       # a cycle is assumed to return
    f = explore(fva)
    if not f.insns or f.trunc or f.indirect:
        return False
    tail_at = dict((a, t) for a, t in f.tails)
    seen, work, returns = set(), [fva], False
    while work and not returns:
        va = work.pop()
        if va in seen:
            continue
        seen.add(va)
        ins = f.insns.get(va)
        if ins is None or va in f.rets:
            returns = True
            break
        if va in tail_at:
            if not is_noreturn(tail_at[va], seed, depth + 1):
                returns = True
                break
            continue
        if ins.mn == 'call' and ins.ops[0][0] == 'imm':
            if is_noreturn(ins.ops[0][1], seed, depth + 1):
                continue
        work.extend(f.succ.get(va, ()))
    _noret[key] = not returns
    return not returns


def noreturn_set(fns, seed=NORETURN_SEED):
    cur, cands = set(seed), set()
    for fva in fns:
        f = explore(fva)
        cands.update(t for _, t in f.calls if t)
        cands.update(t for _, t in f.tails)
    for _ in range(4):
        grew = False
        for t in sorted(cands - cur):
            _noret.clear()
            if is_noreturn(t, frozenset(cur)):
                cur.add(t)
                grew = True
        if not grew:
            break
    return frozenset(cur)


# ------------------------------------------------------------------ analysis
def _cap(s):
    return None if s is None or len(s) > VCAP else frozenset(s)


def _merge(a, b):
    ra, pa = a
    rb, pb = b
    rr = tuple(None if (x is None or y is None) else _cap(x | y) for x, y in zip(ra, rb))
    if pa is None or pb is None:
        pp = None
    else:
        u = pa | pb
        pp = None if len(u) > PCAP else u
    return (rr, pp)


NON_WRITERS = frozenset(('cmp', 'test', 'push', 'bt', 'comiss', 'ucomiss', 'comisd', 'ucomisd',
                         'jmp', 'call', 'out', 'nop', 'bound', 'arpl', 'verr', 'verw'))
IMPLICIT = {
    'cdq': ('edx',), 'cwd': ('edx', 'eax'), 'cwde': ('eax',), 'cbw': ('eax',),
    'lahf': ('eax',), 'rdtsc': ('eax', 'edx'), 'cpuid': ('eax', 'ebx', 'ecx', 'edx'),
    'xlat': ('eax',), 'in': ('eax',), 'leave': ('esp', 'ebp'), 'enter': ('esp', 'ebp'),
    'pusha': ('esp',), 'popa': tuple(REGS), 'popad': tuple(REGS),
    'movs': ('esi', 'edi', 'ecx'), 'stos': ('edi', 'ecx'), 'scas': ('edi', 'ecx'),
    'cmps': ('esi', 'edi', 'ecx'), 'lods': ('esi', 'eax', 'ecx'), 'ins': ('edi', 'ecx'),
    'outs': ('esi', 'ecx'), 'loop': ('ecx',), 'loope': ('ecx',), 'loopne': ('ecx',),
    'fnstsw': ('eax',), 'fstsw': ('eax',), 'salc': ('eax',), 'aaa': ('eax',), 'aas': ('eax',),
    'aam': ('eax',), 'aad': ('eax',), 'daa': ('eax',), 'das': ('eax',), 'cmpxchg': ('eax',),
    'push': ('esp',), 'pop': ('esp',), 'call': ('esp',), 'ret': ('esp',),
}


def written(ins):
    """Registers (full names) the instruction writes."""
    m, ops = ins.mn, ins.ops
    w = set(IMPLICIT.get(m, ()))
    if m in ('mul', 'div', 'idiv') or (m == 'imul' and len(ops) == 1):
        w.update(('eax', 'edx'))
    if m == 'fnstsw' or m == 'fstsw':
        return w
    if ops and ops[0][0] == 'reg' and m not in NON_WRITERS and not m.startswith('j'):
        w.add(PARENT[ops[0][1]])
    if m in ('xchg', 'xadd', 'cmpxchg') and len(ops) > 1 and ops[1][0] == 'reg':
        w.add(PARENT[ops[1][1]])
    return w


class Shape:
    __slots__ = ('arity_set', 'kinds', 'argc', 'argc_top', 'argc_delegated',
                 'push_agree', 'gettop', 'live_rets', 'dead_rets', 'stack_delta',
                 'edges_indirect', 'edges_trunc', 'capped')


def _pop(pushes, n):
    if n < 0:
        return None
    out = set()
    for tr in pushes:
        if n > len(tr):
            return None
        out.add(tr[:len(tr) - n] if n else tr)
    return frozenset(out) if len(out) <= PCAP else None


def analyse(entry, noret, delegators):
    f = explore(entry)
    S = Shape()
    S.edges_indirect, S.edges_trunc, S.capped = len(f.indirect), f.trunc, False
    init = (tuple(None for _ in REGS), frozenset({()}))
    state, work, ret_state = {entry: init}, [entry], {}
    idx_hits, saw_gettop, guard = [], False, 0
    delegated = False
    while work:
        guard += 1
        if guard > 250000:
            S.capped = True
            break
        va = work.pop()
        st = state.get(va)
        ins = f.insns.get(va)
        if st is None or ins is None:
            continue
        regs = dict(zip(REGS, st[0]))
        pushes, m, ops = st[1], ins.mn, ins.ops
        if va in f.rets:
            ret_state.setdefault(va, []).append((regs['eax'], pushes))
            continue
        nr = dict(regs)
        for p in written(ins):
            nr[p] = None

        def rd(o):
            if o[0] == 'imm':
                return frozenset({o[1]})
            if o[0] == 'reg':
                return regs.get(o[1])
            return None

        if m == 'mov' and len(ops) == 2 and ops[0][0] == 'reg':
            dn = ops[0][1]
            p = PARENT[dn]
            if dn == p:
                nr[p] = _cap(rd(ops[1]))
            elif dn in ('al', 'bl', 'cl', 'dl') and ops[1][0] == 'imm' \
                    and regs[p] is not None:
                v = ops[1][1] & 0xFF
                nr[p] = _cap({(x & 0xFFFFFF00) | v for x in regs[p]})
        elif m in ('xor', 'sub') and len(ops) == 2 and ops[0][0] == 'reg' \
                and ops[1][0] == 'reg' and ops[0][1] == ops[1][1]:
            dn = ops[0][1]
            if dn == PARENT[dn]:
                nr[dn] = frozenset({0})
        elif m in ('add', 'sub', 'and', 'or', 'xor') and len(ops) == 2 \
                and ops[0][0] == 'reg' and ops[1][0] == 'imm':
            dn = ops[0][1]
            p, k = PARENT[dn], ops[1][1]
            if dn == p and m == 'or' and k == M32:
                nr[p] = frozenset({M32})
            elif dn == p and m == 'and' and k == 0:
                nr[p] = frozenset({0})
            elif dn == p and regs[p] is not None:
                fn_ = {'add': lambda a: (a + k) & M32, 'sub': lambda a: (a - k) & M32,
                       'and': lambda a: a & k, 'or': lambda a: a | k,
                       'xor': lambda a: a ^ k}[m]
                nr[p] = _cap({fn_(x) for x in regs[p]})
        elif m in ('inc', 'dec') and ops and ops[0][0] == 'reg':
            dn = ops[0][1]
            p = PARENT[dn]
            if dn == p and regs[p] is not None:
                d = 1 if m == 'inc' else -1
                nr[p] = _cap({(x + d) & M32 for x in regs[p]})
        elif m == 'lea' and len(ops) == 2 and ops[1][0] == 'mem' and ops[0][0] == 'reg':
            dn = ops[0][1]
            p = PARENT[dn]
            _, base, index, _, disp = ops[1]
            if dn == p and index is None:
                if base is None:
                    nr[p] = frozenset({disp & M32})
                elif base in REGS and regs[base] is not None:
                    nr[p] = _cap({(x + disp) & M32 for x in regs[base]})

        npush = pushes
        if m == 'call':
            t = ops[0][1] if ops[0][0] == 'imm' else None
            nr['eax'] = nr['ecx'] = nr['edx'] = None        # caller-saved
            if t is not None:
                if t in IDX_READERS:
                    idx_hits.append(regs['edx'])
                if t == GETTOP:
                    saw_gettop = True
                if t in delegators:
                    delegated = True
                if t in POPS_N and pushes is not None:
                    npush = _pop(pushes, POPS_N[t])
                elif t == SETTOP and pushes is not None:
                    ev = regs['edx']
                    if ev is not None and len(ev) == 1:
                        raw = next(iter(ev))
                        k = raw - (1 << 32) if raw >> 31 else raw
                        npush = _pop(pushes, -k - 1) if k < 0 else None
                    else:
                        npush = None
                elif t in REPLACE_TOP and pushes is not None:
                    kind = REPLACE_TOP[t]
                    nn, ok = set(), True
                    for tr in pushes:
                        if not tr:      # the key was not one of our own pushes
                            ok = False
                            break
                        nn.add(tr[:-1] + (kind,))
                    npush = frozenset(nn) if ok and len(nn) <= PCAP else None
                elif (LAPI_LO <= t < LAPI_HI and t not in NEUTRAL_READERS
                      and t not in PUSHERS and t not in POPS_N
                      and t not in (SETTOP, GETTOP)):
                    npush = None                             # unmodelled stack op
                elif t in PUSHERS and pushes is not None:
                    kind = PUSHERS[t]
                    if t == PUSHSTRING:
                        ev = regs['edx']
                        lit = (ev is not None and ev
                               and all(v and cstr(v) is not None for v in ev))
                        if not lit:
                            kind = 'string?'
                    nn, ok = set(), True
                    for tr in pushes:
                        if len(tr) >= LCAP:
                            ok = False
                            break
                        nn.add(tr + (kind,))
                    npush = frozenset(nn) if ok and len(nn) <= PCAP else None
                if t in noret:
                    continue                                 # no fall-through

        newst = (tuple(nr[r] for r in REGS), npush)
        for s in f.succ.get(va, ()):
            old = state.get(s)
            if old is None:
                state[s] = newst
                work.append(s)
            else:
                mg = _merge(old, newst)
                if mg != old:
                    state[s] = mg
                    work.append(s)

    S.live_rets, S.dead_rets = sorted(ret_state), [r for r in f.rets if r not in ret_state]
    eaxs, kinds, agree, deltas = [], set(), [], set()
    for r in S.live_rets:
        for ea, pu in ret_state[r]:
            eaxs.append(ea)
            if pu is None:
                kinds.add(None)
            else:
                kinds.update(pu)
            if ea is not None and pu is not None:
                agree.append({len(tr) for tr in pu} == set(ea))
                deltas.update(len(tr) - e for tr in pu for e in ea)
            elif pu is not None:
                # this ret contributed kinds but its eax never folded to a constant, so the
                # cross-check was not run on it: `agree` must not hold
                agree.append(False)
    if not eaxs or any(e is None for e in eaxs):
        S.arity_set = None
    else:
        u = set()
        for e in eaxs:
            u |= set(e)
        S.arity_set = frozenset(u)
    S.kinds = None if (None in kinds or not kinds) else frozenset(kinds)
    S.push_agree = (all(agree) if agree else None)
    S.stack_delta = (next(iter(deltas)) if len(deltas) == 1 else None)
    pos = [v for s in idx_hits if s for v in s if 0 < v < 0x1000]
    S.argc = max(pos) if pos else 0
    S.argc_top = any(s is None for s in idx_hits)
    S.argc_delegated = delegated
    S.gettop = saw_gettop
    return S


def find_pushing_callees(binding_fns, noret):
    """A callee that pushes on the binding's behalf is invisible to the binding's trace, which
    can then match eax in length while describing the wrong slots. Declared, not corrected: one
    call deep, so a floor."""
    out = set()
    for fva in binding_fns:
        f = explore(fva)
        for t in set(c for _, c in f.calls if c) | set(t for _, t in f.tails):
            if t in noret or LAPI_LO <= t < LAPI_HI or not is_code(t):
                continue
            g = explore(t)
            if any(c in PUSHERS for _, c in g.calls if c) \
                    or any(c in PUSHERS for _, c in g.tails):
                out.add(fva)
                break
    return out


def find_delegators(binding_fns, noret):
    """A binding whose argument parsing is done by a callee reports argc as a silent lower
    bound. The detector: a direct callee, not itself a modelled helper, that reads a Lua stack
    index. One call deep, so argc stays a floor even on rows marked exact."""
    modelled = (set(IDX_READERS) | set(PUSHERS) | set(POPS_N) | set(REPLACE_TOP)
                | {SETTOP, GETTOP} | noret)
    cands = set()
    for fva in binding_fns:
        f = explore(fva)
        cands.update(t for _, t in f.calls if t and t not in modelled)
        cands.update(t for _, t in f.tails if t not in modelled)
    out = set()
    for t in sorted(cands):
        if not is_code(t):
            continue
        g = explore(t)
        if any(c in IDX_READERS for _, c in g.calls if c):
            out.add(t)
    return out


# ------------------------------------------------------------------ output
def fmt_kinds(kinds):
    if kinds is None:
        return '?'
    return ' | '.join(sorted(('(' + ','.join(t) + ')') if t else '()' for t in kinds))


def main():
    args = parse_args(__doc__, disasm=True)
    dis = Disasm(args.disasm)
    dis.exe = args.exe
    setup(Image(args.exe), dis)
    tables, unresolved = harvest()

    rowlist = []                      # (name, fn, pair, table, kind)
    for base in sorted(tables):
        t = tables[base]
        for pva, nm, fp in t['rows']:
            rowlist.append((nm, fp, pva, base, t['kind']))
    fns = sorted({fp for _, fp, _, _, _ in rowlist if is_code(fp)})

    noret = noreturn_set(fns)
    delegators = find_delegators(fns, noret)
    pushing_callees = find_pushing_callees(fns, noret)

    shapes = {fva: analyse(fva, noret, delegators) for fva in fns}

    namecount = {}
    for nm, _, _, _, _ in rowlist:
        namecount[nm] = namecount.get(nm, 0) + 1

    out = []
    for nm, fva, pva, base, kind in sorted(rowlist, key=lambda r: (r[0] or '', r[1])):
        S = shapes.get(fva)
        if S is None:
            continue
        if S.arity_set is None:
            arity, aconf = '?', 'unknown'
        elif len(S.arity_set) == 1:
            arity, aconf = str(next(iter(S.arity_set))), 'exact'
        else:
            arity, aconf = '|'.join(str(v) for v in sorted(S.arity_set)), 'set'
        if S.kinds is None:
            kinds, kconf = '?', 'unknown'
        elif S.push_agree:
            kinds, kconf = fmt_kinds(S.kinds), 'agree'
        else:
            kinds, kconf = fmt_kinds(S.kinds), 'unverified'
        aeconf = 'lower-bound' if (S.argc_delegated or S.argc_top) else 'exact'
        notes = []
        if (S.arity_set is not None and len(S.arity_set) == 1
                and S.stack_delta is not None and S.stack_delta > 0
                and len(S.live_rets) == 1):
            notes.append('stack-leak')
        if S.gettop and S.arity_set is None:
            notes.append('variadic')
        if namecount.get(nm, 0) > 1:
            notes.append('name-not-unique')
        if fva in pushing_callees:
            notes.append('delegated-push')
        if S.capped:
            notes.append('iteration-cap')
        if S.edges_trunc:
            notes.append('cfg-truncated')
        if S.edges_indirect:
            notes.append('indirect-branch')
        out.append((nm or '?', addr(fva), addr(pva), addr(base), kind, S.argc, aeconf,
                    arity, aconf, kinds, kconf, ';'.join(notes)))

    bad = sum(1 for r in out if any(x in r[-1] for x in ('cfg-truncated', 'indirect-branch',
                                                         'iteration-cap')))
    note('%d registrar tables, %d bindings, %d unresolved registrar sites, %d rows with an '
         'unsound edge' % (len(tables), len(out), len(unresolved), bad))
    write_table(['name', 'fn', 'pair', 'table', 'table_kind', 'argc', 'argc_conf', 'arity',
                 'arity_conf', 'kinds', 'kinds_conf', 'notes'], out, args.out)


if __name__ == '__main__':
    sys.exit(main())
