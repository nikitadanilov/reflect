"""
source ~/p/ref/ref.py
reflect
"""

import gdb
import inspect
import sortedcontainers

class rmap(): # reflective memory map
        def __init__(self):
                self.mem = sortedcontainers.SortedList(key = lambda pair: pair[0])
        def at(self, addr):
                return [o for (_, o) in self.mem.irange((addr, None), (addr, None), (True, True))]
        def get(self, ro):
                addr = ro.addr()
                for other in self.at(addr):
                        print(other.addr(), addr) if other.addr() != addr else 0
                        assert other.addr() == addr
                        if other == ro or (type(ro) == type(other) and \
                                           other.same(ro)):
                                return other
                self.mem.add((addr, ro))
                return ro

class robj: # reflective object
        def __init__(self, rm):
                self.rm    = rm
                self.link  = []
                self.canon = None
                self.mark  = False
        def addr(self):
                return -1
        def end(self):
                return 0
        def same(self, other):
                return  self.end() == other.end() and \
                        sametype(self.type(), other.type())
        def children(self):
                pass
        def name(self):
                return self.canon.to()
        def type(self):
                return ''
        def kind(self):
                return ''
        def add(self, l):
                if all(not l.same(scan) for scan in self.link):
                        self.link.append(l)
                        if not self.canon or len(l.to()) < len(self.canon.to()):
                                self.canon = l
        def names(self):
                return [l.to() for l in self.link]
        def descr(self):
                return ''

class rlink: # reflective link between reflective objects
        def __init__(self, src, dst, name, embed):
                self.src = src
                self.dst = src.rm.get(dst)
                self.name = name
                self.embed = embed
                self.dst.add(self)
        def to(self):
                return self.src.name() + self.name
        def same(self, other):
                return self.src == other.src and self.name == other.name

def sametype(t0, t1):
        return  t0 == t1 or \
                (t0 and t1 and \
                 t0.alignof == t1.alignof and \
                 t0.code    == t1.code and \
                 t0.dynamic == t1.dynamic and \
                 t0.name    == t1.name and \
                 t0.sizeof  == t1.sizeof and \
                 t0.tag     == t1.tag)

class rroot(robj):
        def __init__(self, rm):
                super().__init__(rm)
                rm.get(self)
        def name(self):
                return '/'
        def same(self, other):
                return self == other
        def children(self):
                return [rlink(self, rthread(self.rm, t),
                              't' + str(t.num), False)
                        for t in gdb.selected_inferior().threads()]

class rthread(robj):
        def __init__(self, rm, thread):
                super().__init__(rm)
                self.thread = thread
        def same(self, other):
                return self.thread.num == other.thread.num
        def children(self):
                frames = []
                t0 = gdb.selected_thread()
                f0 = gdb.selected_frame()
                self.thread.switch()
                frame = gdb.newest_frame()
                while frame != None and frame.is_valid():
                        frames.append(frame)
                        frame = frame.older()
                t0.switch()
                f0.select()
                return [rlink(self, rframe(self.rm, f, self), '.f[' + str(f.level()) + ']',
                              False) for f in frames]

class rframe(robj):
        def __init__(self, rm, frame, thread):
                super().__init__(rm)
                self.frame  = frame
                self.thread = thread
        def addr(self):
                return self.frame.block().start
        def end(self):
                return self.frame.block().end
        def same(self, other):
                return  self.thread.same(other.thread) and \
                        self.frame.level == other.frame.level
        def name(self):
                function = (self.frame.name() + '()') if self.frame.name() else ''
                return super().name() + ':' + function
        def children(self):
                sal   = self.frame.find_sal()
                symt  = sal.symtab
                prog  = gdb.current_progspace()
                return  [rlink(self, rblock(self.rm, b, f, n), '', False)
                         for (b, f, n) in ([(self.frame.block(),    self, self.name() + '.text')] + \
                                           [(prog.block_for_pc(pc), self, '')
                                            for pc in range(sal.pc, sal.last)])] + \
                        makechildren(self, symtabclosure(symt, []))

def blockrange(start, end, already):
        return [(p, s, "@" + hex(pc) + ':' + n) for pc in range(start, end)
                for (p, s, n) in blockclosure(gdb.current_progspace().block_for_pc(pc), already)]

def blockclosure(block, already):
        if block == None or any(block.start == b.start and block.end == b.end for b in already):
                return []
        else:
                already.append(block)
                return  blockclosure(block.superblock,   already) + \
                        blockclosure(block.global_block, already) + \
                        blockclosure(block.static_block, already) + \
                        blockrange(block.start, block.end, already) + \
                        [(block, s, s.name) for s in block if not s.needs_frame]

def symtabclosure(symtab, already):
        prev = None
        links = blockclosure(symtab.global_block(), already) + \
                blockclosure(symtab.static_block(), already)
        for line in symtab.linetable():
                if prev:
                        links.extend([(p, s, "#" + str(line.line) + n)
                                      for (p, s, n) in blockrange(prev, line.pc, already)])
                prev = line.pc
        return links

def enumname(module, prefix, val):
        try:
                return next(n for n, v in vars(module).items() if v == val and n.startswith(prefix))
        except StopIteration:
                return "Unknown: {}".format(val)

def symval(sym, frame):
        if sym.addr_class != gdb.SYMBOL_LOC_TYPEDEF:
                if frame != None and frame.frame != None:
                        val = sym.value(frame.frame)
                else:
                        val = sym.value()
        else:
                val = None
        return val

def makechildren(ro, links):
        return [rlink(rblock(ro.rm, p, None, ''), rval(ro.rm, symval(s, None)), n, True) for (p, s, n) in links]

class rblock(robj):
        def __init__(self, rm, block, frame, name):
                super().__init__(rm)
                self.block = block
                self.frame = frame
                self.n     = name
        def addr(self):
                return self.block.start
        def end(self):
                return self.block.end
        def same(self, other):
                return self.block.end == other.block.end and self.frame == other.frame
        def name(self):
                return self.n
        def symname(self, sym):
                return sym.symtab.filename + ":" + str(sym.line) + ":" + sym.name
        def children(self):
                parent = self.frame if self.frame != None else self
                return [rlink(parent, rval(self.rm, symval(sym, self.frame)), ':' + self.symname(sym), False)
                        for sym in self.block] + makechildren(self, blockclosure(self.block, []))


class rval(robj):
        def __init__(self, rm, val):
                super().__init__(rm)
                self.val = val
                try:
                        self.a = int(str(val.reference_value())[1:], 16)
                except Exception:
                        self.a = -1
                try:
                        self.printname = str(val)
                except gdb.MemoryError:
                        self.printname = '<invalid>'
        def addr(self):
                return self.a
        def end(self):
                return (self.a + self.val.type.sizeof) if self.a != -1 else -1
        def type(self):
                return self.val.type if self.val != None else None
        def descr(self):
                return self.printname
        def kind(self):
                return enumname(gdb, 'TYPE_CODE_', self.val.type.code) if self.val != None else 'nil'
        def valwrap(self, code, idx, field):
                try:
                        if code == gdb.TYPE_CODE_PTR:
                                name, embed = '*', False
                                target = self.val.dereference()
                        elif code == gdb.TYPE_CODE_ARRAY:
                                name, embed = '[' + str(idx) + ']', True
                                target = self.val[idx]
                        elif code == gdb.TYPE_CODE_STRUCT or \
                             code == gdb.TYPE_CODE_UNION:
                                name, embed = '.' + field.name, True
                                target = self.val[field]
                        elif code == gdb.TYPE_CODE_REF:
                                name, embed = '*', False
                                target = self.val.referenced_value()
                        child = rval(self.rm, target)
                except gdb.MemoryError:
                        child = rill(self.rm)
                return (child, name, embed)
        def children(self):
                val = self.val
                if val == None or val.type == None:
                        return []
                t = val.type
                if t.code == gdb.TYPE_CODE_PTR or \
                   t.code == gdb.TYPE_CODE_REF:
                        kids = [self.valwrap(t.code, 0, None)]
                elif t.code == gdb.TYPE_CODE_ARRAY:
                        kids = [self.valwrap(t.code, i, None) \
                                for i in range(t.range()[0], t.range()[1] + 1)]
                elif t.code == gdb.TYPE_CODE_STRUCT or \
                     t.code == gdb.TYPE_CODE_UNION:
                        kids = [self.valwrap(t.code, 0, field) \
                                for field in t.fields()]
                elif t.code in [gdb.TYPE_CODE_FLAGS,
                                gdb.TYPE_CODE_ENUM,
                                gdb.TYPE_CODE_FUNC,
                                gdb.TYPE_CODE_INT,
                                gdb.TYPE_CODE_FLT,
                                gdb.TYPE_CODE_VOID,
                                gdb.TYPE_CODE_RANGE,
                                gdb.TYPE_CODE_STRING,
                                gdb.TYPE_CODE_FLAGS,
                                gdb.TYPE_CODE_FUNC,
                                gdb.TYPE_CODE_INT,
                                gdb.TYPE_CODE_FLT,
                                gdb.TYPE_CODE_VOID,
                                gdb.TYPE_CODE_SET,
                                gdb.TYPE_CODE_RANGE,
                                gdb.TYPE_CODE_STRING,
                                gdb.TYPE_CODE_BITSTRING,
                                gdb.TYPE_CODE_ERROR,
                                gdb.TYPE_CODE_METHOD,
                                gdb.TYPE_CODE_METHODPTR,
                                gdb.TYPE_CODE_MEMBERPTR,
                                gdb.TYPE_CODE_RVALUE_REF,
                                gdb.TYPE_CODE_CHAR,
                                gdb.TYPE_CODE_BOOL,
                                gdb.TYPE_CODE_COMPLEX,
                                gdb.TYPE_CODE_TYPEDEF,
                                gdb.TYPE_CODE_NAMESPACE,
                                gdb.TYPE_CODE_DECFLOAT,
                                gdb.TYPE_CODE_INTERNAL_FUNCTION]:
                        kids = []
                else:
                        print('0!!!')
                        assert(0)
                return [rlink(self, child, name, embed) for (child, name, embed) in kids]

class rill(robj):
        def __init__(self, rm):
                super().__init__(rm)
        def children(self):
                return []
        def name(self):
                return '<ill>'

class reflect(gdb.Command):
        """Test.
Documented.
        """
        def __init__(self):
                gdb.Command.__init__(self, 'reflect',
                                     gdb.COMMAND_SUPPORT, gdb.COMPLETE_SYMBOL)

        def invoke(self, arg, from_tty):
                self.scanall()
        def scanall(self):
                self.rm = rmap()
                self.front = {rroot(self.rm)}
                self.closure()
                self.printfront()
                #self.graph()
        def closure(self):
                while len(self.front) > 0:
                        ro = self.front.pop()
                        if ro in self.front or ro.mark:
                                print(ro.descr())
                                self.printfront()
                        assert ro not in self.front and not ro.mark
                        ro.mark = True
                        self.front |= {l.dst for l in ro.children() if not l.dst.mark}
        def graph(self):
                idx = {}
                n = 0
                for (addr, ro) in self.rm.mem:
                        idx[ro] = n
                        n += 1
                for (addr, ro) in self.rm.mem:
                        print('    n{} [label="{:x}"]'.format(idx[ro], ro.addr()))
                for (addr, ro) in self.rm.mem:
                        for l in ro.link:
                                print('    n{} -> n{} [label="{}"]'.format(idx[l.src], idx[ro], l.name))
        def printfront(self):
                for (addr, ro) in self.rm.mem:
                        print('{:14x} {:32}: {:20} {:12} {} {}'.format(addr, ro.name(), ro.descr(), ro.kind(), ro.type(), 
                                                                       [n for n in ro.names() if n != ro.name()]))

reflect()
gdb.execute('set height 0')
print('reflect loaded.')
