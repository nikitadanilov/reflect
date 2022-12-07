# (gdb) pi {print(s.name, str(v), str(v.address)) for (s, v) in reflect().invoke(0, 0)}

import gdb
import sortedcontainers

class reflect(gdb.Command):
        """Test.
Documented.
        """
        def __init__(self):
                gdb.Command.__init__(self, 'reflect',
                                     gdb.COMMAND_SUPPORT, gdb.COMPLETE_SYMBOL)

        def invoke(self, arg, from_tty):
                self.seen = []
                self.root = []
                self.roots()
                self.front = [v for (s, v) in self.root]
                self.closure()

        def closure(self):
                while len(self.front) > 0:
                        val = self.front.pop()
                        self.addval(val)
                        for c in self.children(val):
                                self.front.append(c)

        def roots(self):
                t0 = gdb.selected_thread()
                f0 = gdb.selected_frame()
                for t in gdb.selected_inferior().threads():
                        t.switch()
                        frame = gdb.newest_frame()
                        while frame != None and frame.is_valid():
                                self.frameroots(frame)
                                frame = frame.older()
                t0.switch()
                f0.select()

        def frameroots(self, frame):
                if self.process(frame, frame):
                        sal = frame.find_sal()
                        self.blockroots(frame.block(), frame)
                        self.symtabroots(sal.symtab)
                        self.addrroots(sal.pc, sal.last, frame)

        def blockroots(self, block, frame):
                if self.process(block, (block.start, frame)):
                        for sym in block:
                                self.add(sym, frame)
                        if block.superblock:
                                self.blockroots(block.superblock, None)

        def symtabroots(self, symtab):
                if self.process(symtab, symtab.filename):
                        for sym in symtab.global_block():
                                self.add(sym, None)
                        for sym in symtab.static_block():
                                self.add(sym, None)

        def addrroots(self, start, end, frame):
                prog = gdb.current_progspace()
                while start < end:
                        block = prog.block_for_pc(start)
                        if block:
                                self.blockroots(block, frame)
                        start += 8

        def add(self, sym, frame):
                if self.process(sym, (sym.name, sym.line, frame)):
                        if sym.addr_class != gdb.SYMBOL_LOC_TYPEDEF:
                                if frame:
                                        val = sym.value(frame)
                                else:
                                        val = sym.value()
                                self.root.append((sym, val))
                        self.symtabroots(sym.symtab)

        def process(self, something, marker):
                t = type(something)
                if something.is_valid() and (t, marker) not in self.seen:
                        self.seen.append((t, marker))
                        return True
                else:
                        return False

        def children(self, val):
                t = val.type

reflect()

print('reflect loaded.')
