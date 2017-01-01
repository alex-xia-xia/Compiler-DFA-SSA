import re, collections, copy

from cfg import *
from dfa_framework import DFAFramework

class ReachingDefinitionAnalysis(DFAFramework):
    """docstring for ReachingDefinitionAnalysis"""
    def __init__(self, direction='forward', *args, **kwargs):
        kwargs['direction'] = direction
        super(ReachingDefinitionAnalysis, self).__init__(*args, **kwargs)

    def _set_merge_trans_func(self):
        def merge_func(*args):
            if len(args) == 0:
                return set()
            res = args[0]
            for i in range(1, len(args)):
                res |= args[i]
            return res

        def trans_func(x, gen, kill):
            return (x - kill) | gen

        self.merge_func = merge_func
        self.trans_func = trans_func

    def _calc_top_bottom(self):
        self.top = set()
        self.bottom = set()
        for instr in self.instrs:
            self.bottom.update(instr.RD_GEN)

    def _get_rd_kill(self, lefts):
        res = set()
        for bt in self.bottom: # bt is a tuple of (instr_id, left)
            if bt[1] in lefts:
                res.add(bt)
        return res

    def _calc_gen_kill(self):
        self.GEN = collections.defaultdict(set)
        self.KILL = collections.defaultdict(set)
        for instr in self.instrs:
            instr.RD_KILL.update(self._get_rd_kill(instr.left) - instr.RD_GEN)

        for bbn, bb in self.cfg.bbs.items():
            st, ed = bb.st_instr_id, bb.ed_instr_id
            idx = st
            while idx <= ed:
                instr = self.instrs[idx - 1]
                self.KILL[bbn] |= instr.RD_KILL
                self.KILL[bbn] -= instr.RD_GEN
                self.GEN[bbn] = self.trans_func(self.GEN[bbn], instr.RD_GEN, instr.RD_KILL)
                idx += 1

    def _calc_iter_IN_OUT_for_instr(self):
        super(ReachingDefinitionAnalysis, self)._calc_iter_IN_OUT_for_instr(gen_attr='RD_GEN', kill_attr='RD_KILL')

    def _constant_propagation(self):
        self.num_propagation = 0
        for instr in self.instrs:
            pass


    def _optimize(self):
        self._constant_propagation()




