import re, collections, copy

class Instruction(object):
    '''
    Naming rules:
    BR: branches
    PROC: procedure call, ret
    '''
    RET_OPS = ['ret']
    BR_OPS = ['br', 'blbc', 'blbs']
    PROC_OPS = ['call'] + RET_OPS
    PROC_START_OP = 'enter'
    JMP_OPS = BR_OPS + ['call'] # although 'ret' is also a jump, it does not have explicit dst addr in the instruction
    CBR_OPS = ['blbc', 'blbs'] # conditional branch
    CJMP_OPS = CBR_OPS
    UBR_OPS = ['br'] # unconditional branch
    UJMP_OPS = UBR_OPS + ['call'] # although 'ret' is also a jump, it does not have explicit dst addr in the instruction
    LEADER_OPS = ['enter']
    INVALID_LEADER_OPS = ['entrypc', 'nop']
    TERMINATOR_OPS = BR_OPS + PROC_OPS
    CMP_OPS = ['cmpeq', 'cmple', 'cmplt']
    CALC_OPS = ['add', 'sub', 'mul', 'div', 'mod', 'neg']
    ARITH_OPS = ['add', 'sub', 'mul', 'div', 'mod', 'neg', 'cmpeq', 'cmple', 'cmplt']

    REGISTER_PATTERN = '\((\d+)\)' # e.g. (5)
    INSTR_PATTERN = '\[(\d+)\]' # e.g. [5]
    NUM_PATTERN = '(\d+)' # e.g. 5
    BASE_PATTERN = '[_a-zA-Z0-9]+_base#([-0-9]+)'  # e.g. global_array_base#32576
    OFFSET_PATTERN = '[_a-zA-Z0-9]+_offset#([-0-9]+)' # e.g. y_offset#8
    VAR_PATTERN = '([_a-zA-Z0-9]+)#[-0-9]+' # e.g. i#-8
    PATTERNS = {'r':REGISTER_PATTERN, 'i':INSTR_PATTERN, 'n':NUM_PATTERN, 'b':BASE_PATTERN,
    'o':OFFSET_PATTERN, 'v':VAR_PATTERN}

    def __init__(self, instr_id, op, operand1, operand2):
        super(Instruction, self).__init__()
        self.instr_id = instr_id # integer starting from 1
        self.op = op
        self.operand1 = operand1
        self.operand2 = operand2
        self.left = set()
        self.right = ''
        self._parse()
        self._calc_rd_gen_kill()
        self._calc_ae_gen_kill()
        self._calc_lv_gen_kill()

    def __repr__(self):
        res = 'instr %s:\t' % (self.instr_id)
        if self.op in Instruction.ARITH_OPS + ['move', 'load', 'store']:
            res += '%s = %s' % (' = '.join(self.left), self.right)
        else:
            res += ' '.join([self.op, self.operand1, self.operand2])
        return res

    def _parse_operand(self, operand):
        for k, pat in Instruction.PATTERNS.items():
            m = re.match(pat, operand)
            if m != None:
                res = m.group(1)
                if k == 'r':
                    return k, 'r' + res
                elif k == 'i':
                    return k, int(res)
                return k, res

        return '', operand

    def _parse(self):
        self.operand1_parsed = self._parse_operand(self.operand1)[1]
        self.operand2_parsed = self._parse_operand(self.operand2)[1]
        if self.op in Instruction.ARITH_OPS:
            self.operands = (self.operand1_parsed, self.operand2_parsed)
            self.right = '%s %s %s' % (self.operand1_parsed, self.op, self.operand2_parsed)
            self.left.add('r%s' % self.instr_id)
        elif self.op == 'move':
            self.right = self.operand1_parsed
            self.left.add(self.operand2_parsed)
            self.left.add('r%s' % self.instr_id)
        elif self.op == 'load':
            self.right = self.operand1_parsed
            self.left.add('r%s' % self.instr_id)
        elif self.op == 'store':
            self.right = self.operand1_parsed
            self.left.add('*(%s)' % self.operand2_parsed)
        elif self.op in Instruction.CJMP_OPS:
            self.dst_bbn = self.operand2_parsed
        elif self.op in Instruction.UJMP_OPS:
            self.dst_bbn = self.operand1_parsed

    def _calc_rd_gen_kill(self):
        self.RD_VAR_KILL = self.left
        self.RD_KILL = set()
        self.RD_GEN = set() if self.op == 'store' else {(self.instr_id, lft) for lft in self.left}

    def _calc_ae_gen_kill(self):
        self.AE_VAR_KILL = self.left
        self.AE_KILL = set()
        self.AE_GEN = set()
        if self.op in Instruction.ARITH_OPS:
            rights = self.operands
            for lf in self.left:
                if lf in rights:
                    self.AE_KILL.add(self.right)
                    return
            self.AE_GEN.add(self.right)

    def _calc_lv_gen_kill(self):
        is_variable = lambda x : x not in ['GP', 'FP'] and re.match('\d+', x) == None
        self.LV_GEN = set()
        if self.op in Instruction.ARITH_OPS:
            for v in self.operands:
                if is_variable(v):
                    self.LV_GEN.add(v)
        elif self.op in ['move', 'load']:
            self.LV_GEN.add(self.right)
        elif self.op == 'store':
            if is_variable(self.right):
                self.LV_GEN.add(self.right)
            if is_variable(self.operand2_parsed):
                self.LV_GEN.add(self.operand2_parsed)
        self.LV_KILL = self.left - self.LV_GEN


def read_3addr_code_from_file(file_name, skip_num_rows=0):
    '''
    skip_num_rows: default value is 0.
    Although the first line is "compiling examples/*.c", this line is not included if we redirect the output to file.
    '''
    instr_strs = list()
    with open(file_name) as fin:
        instr_strs = [line.strip() for line in fin.readlines()]
        instr_strs = instr_strs[skip_num_rows:]
    return instr_strs

def read_instrs(file_name, skip_num_rows=0):
    instr_strs = read_3addr_code_from_file(file_name, skip_num_rows=skip_num_rows)
    try:
        instrs = list()
        for instr_str in instr_strs:
            cols = instr_str.split()
            cols.extend([''] * (5 - len(cols)))
            instrs.append(Instruction(int(cols[1][:-1]), cols[2], cols[3], cols[4]))
    except Exception, e:
        print e
        print 'Bad instructions in the code!'
    return instrs
