import simuvex

from ..analysis import Analysis, register_analysis
from ..project import Hook

import logging
l = logging.getLogger('angr.analyses.callee_cleanup_finder')

class CalleeCleanupFinder(Analysis):
    def __init__(self, starts=None, hook_all=False):
        self.results = {}

        for addr in starts:
            with self._resilience():
                size = self.analyze(addr)
                if size is None:
                    l.warning("Couldn't find return for function at %#x", addr)
                else:
                    self.results[addr] = size

        if hook_all:
            for addr, size in self.results.iteritems():
                if size % self.project.arch.bytes != 0:
                    l.error("Function at %#x has a misaligned return?", addr)
                    continue
                args = size / self.project.arch.bytes
                cc = self.project.factory.cc_from_arg_kinds([False]*args)
                cc.CALLEE_CLEANUP = True
                self.project.hook(addr, Hook(simuvex.SimProcedures['stubs']['ReturnUnconstrained'], cc=cc))

    def analyze(self, addr):
        seen = set()
        todo = [addr]

        while todo:
            addr = todo.pop(0)
            seen.add(addr)
            irsb = self.project.factory.block(addr, opt_level=0).vex
            if irsb.jumpkind == 'Ijk_Ret':
                # got it!
                for stmt in reversed(irsb.statements):
                    if stmt.tag == 'Ist_IMark':
                        l.error("VERY strange return instruction at %#x...", addr)
                        break
                    if stmt.tag == 'Ist_WrTmp':
                        if stmt.data.tag == 'Iex_Binop':
                            if stmt.data.op.startswith('Iop_Add'):
                                return stmt.data.args[1].con.value - self.project.arch.bytes
            elif irsb.jumpkind == 'Ijk_Call':
                if addr + irsb.size not in seen:
                    todo.append(addr + irsb.size)
            else:
                todo.extend(irsb.constant_jump_targets - seen)

        return None

register_analysis(CalleeCleanupFinder, 'CalleeCleanupFinder')
