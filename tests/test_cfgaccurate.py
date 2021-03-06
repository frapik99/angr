import nose
import angr
import time
import pickle
import networkx
import simuvex

import logging
l = logging.getLogger("angr.tests.test_cfg")

import os
test_location = str(os.path.join(os.path.dirname(os.path.realpath(__file__)), '../../binaries/tests'))

def compare_cfg(standard, g, function_list):
    """
    Standard graph comes with addresses only, and it is based on instructions, not on basic blocks
    """

    def get_function_name(addr):
        start = 0
        end = len(function_list) - 1

        while start <= end:
            mid = (start + end) / 2
            f = function_list[mid]
            if addr < f['start']:
                end = mid - 1
            elif addr > f['end']:
                start = mid + 1
            else:
                return f['name']

        return None

    # Sort function list
    function_list = sorted(function_list, key=lambda x: x['start'])

    # Convert the IDA-style CFG into VEX-style CFG
    s_graph = networkx.DiGraph()
    all_nodes = sorted(standard.nodes())
    addr_to_basicblock = {}
    last_basicblock = None
    for n in all_nodes:
        if last_basicblock is None:
            last_basicblock = (n, n)

        block = last_basicblock
        successors = standard.successors(n)
        if len(successors) == 1 and successors[0] >= block[0]:
            last_basicblock = (block[0], successors[0])
        else:
            # Save the existing block
            addr_to_basicblock[block[0]] = block

            # Create edges
            for s in successors:
                s_graph.add_edge(block[0], s)

            # Clear last_basicblock so that we create a new basicblock next time
            last_basicblock = None

    graph = networkx.DiGraph()
    for src, dst in g.edges():
        graph.add_edge(src.addr, dst.addr)

    # Graph comparison
    for src, dst in s_graph.edges():
        if graph.has_edge(src, dst):
            continue
        else:
            # Edge doesn't exist in our CFG
            l.error("Edge (%s-0x%x, %s-0x%x) only exists in IDA CFG.", get_function_name(src), src, get_function_name(dst), dst)

    for src, dst in graph.edges():
        if s_graph.has_edge(src, dst):
            continue
        else:
            # Edge doesn't exist in our CFG
            l.error("Edge (%s-0x%x, %s-0x%x) only exists in angr's CFG.", get_function_name(src), src, get_function_name(dst), dst)

def perform_single(binary_path, cfg_path=None):
    proj = angr.Project(binary_path,
                        use_sim_procedures=True,
                        default_analysis_mode='symbolic',
                        load_options={'auto_load_libs': False})
    start = time.time()
    cfg = proj.analyses.CFGAccurate(context_sensitivity_level=1)
    end = time.time()
    duration = end - start
    bbl_dict = cfg.get_bbl_dict()

    l.info("CFG generated in %f seconds.", duration)
    l.info("Contains %d members in BBL dict.", len(bbl_dict))

    if cfg_path is not None and os.path.isfile(cfg_path):
        # Compare the graph with a predefined CFG
        info = pickle.load(open(cfg_path, "rb"))
        standard = info['cfg']
        functions = info['functions']
        graph = cfg.graph

        compare_cfg(standard, graph, functions)
    else:
        l.warning("No standard CFG specified.")

def test_cfg_0():
    binary_path = test_location + "/x86_64/cfg_0"
    cfg_path = binary_path + ".cfg"
    perform_single(binary_path, cfg_path)

def test_cfg_1():
    binary_path = test_location + "/x86_64/cfg_1"
    cfg_path = binary_path + ".cfg"
    perform_single(binary_path, cfg_path)

def test_cfg_2():
    binary_path = test_location + "/armel/test_division"
    cfg_path = binary_path + ".cfg"
    perform_single(binary_path, cfg_path)

def test_cfg_3():
    binary_path = test_location + "/mips/test_arrays"
    cfg_path = binary_path + ".cfg"
    perform_single(binary_path, cfg_path)

def disabled_cfg_4():
    binary_path = test_location + "/mipsel/darpa_ping"
    cfg_path = binary_path + ".cfg"
    perform_single(binary_path, cfg_path)

def test_additional_edges():
    # Test the `additional_edges` parameter for CFG generation

    binary_path = test_location + "/x86_64/switch"
    proj = angr.Project(binary_path,
                        use_sim_procedures=True,
                        default_analysis_mode='symbolic',
                        load_options={'auto_load_libs': False})
    additional_edges = {
        0x400573 : [ 0x400580, 0x40058f, 0x40059e ]
    }
    cfg = proj.analyses.CFGAccurate(context_sensitivity_level=0, additional_edges=additional_edges)

    nose.tools.assert_not_equal(cfg.get_any_node(0x400580), None)
    nose.tools.assert_not_equal(cfg.get_any_node(0x40058f), None)
    nose.tools.assert_not_equal(cfg.get_any_node(0x40059e), None)
    nose.tools.assert_equal(cfg.get_any_node(0x4005ad), None)

def test_not_returning():
    # Make sure we are properly labeling functions that do not return in function manager

    binary_path = test_location + "/x86_64/not_returning"
    proj = angr.Project(binary_path,
                        use_sim_procedures=True,
                        load_options={'auto_load_libs': False}
                        )
    cfg = proj.analyses.CFGAccurate(context_sensitivity_level=0)  # pylint:disable=unused-variable

    # function_a returns
    nose.tools.assert_not_equal(proj.kb.functions.function(name='function_a'), None)
    nose.tools.assert_true(proj.kb.functions.function(name='function_a').returning)

    # function_b does not return
    nose.tools.assert_not_equal(proj.kb.functions.function(name='function_b'), None)
    nose.tools.assert_false(proj.kb.functions.function(name='function_b').returning)

    # function_c does not return
    nose.tools.assert_not_equal(proj.kb.functions.function(name='function_c'), None)
    nose.tools.assert_false(proj.kb.functions.function(name='function_c').returning)

    # main does not return
    nose.tools.assert_not_equal(proj.kb.functions.function(name='main'), None)
    nose.tools.assert_false(proj.kb.functions.function(name='main').returning)

    # function_d should not be reachable
    nose.tools.assert_equal(proj.kb.functions.function(name='function_d'), None)

def disabled_cfg_5():
    binary_path = test_location + "/mipsel/busybox"
    cfg_path = binary_path + ".cfg"

    perform_single(binary_path, cfg_path)

def test_cfg_6():
    function_addresses = [0xfa630, 0xfa683, 0xfa6d4, 0xfa707, 0xfa754, 0xfa779, 0xfa7a9, 0xfa7d6, 0xfa844, 0xfa857, 0xfa8d9, 0xfa92f, 0xfa959, 0xfa9fb, 0xfabd6, 0xfac61, 0xfacc2, 0xfad29, 0xfaf94, 0xfbd07, 0xfc100L, 0xfc101, 0xfc14fL, 0xfc18e, 0xfc25e, 0xfc261, 0xfc3c6, 0xfc42fL, 0xfc4a3, 0xfc4cf, 0xfc4db, 0xfc5ba, 0xfc5ef, 0xfc5fe, 0xfc611, 0xfc682, 0xfc6b7, 0xfc7fc, 0xfc8a8, 0xfc8e7, 0xfcb42, 0xfcb50, 0xfcb72, 0xfcc3b, 0xfcc7a, 0xfcc8b, 0xfccdc, 0xfd1a3, 0xff06e]

    # We need to add DO_CCALLS to resolve long jmp and support real mode
    simuvex.o.modes['fastpath'] |= {simuvex.s_options.DO_CCALLS}
    binary_path = test_location + "/i386/bios.bin.elf"
    proj = angr.Project(binary_path,
                        use_sim_procedures=True,
                        page_size=1)
    cfg = proj.analyses.CFGAccurate(context_sensitivity_level=1)  # pylint:disable=unused-variable
    nose.tools.assert_greater_equal(set(f for f in proj.kb.functions), set(function_addresses))
    simuvex.o.modes['fastpath'] ^= {simuvex.s_options.DO_CCALLS}

def test_fauxware():
    binary_path = test_location + "/x86_64/fauxware"
    cfg_path = binary_path + ".cfg"

    perform_single(binary_path, cfg_path)

def disabled_loop_unrolling():
    binary_path = test_location + "/x86_64/cfg_loop_unrolling"

    p = angr.Project(binary_path)
    cfg = p.analyses.CFGAccurate()

    cfg.normalize()
    cfg.unroll_loops(5)

    nose.tools.assert_equal(len(cfg.get_all_nodes(0x400636)), 7)

def test_thumb_mode():
    # In thumb mode, all addresses of instructions and in function manager should be odd numbers, which loyally
    # reflect VEX's trick to encode the THUMB state in the address.

    binary_path = test_location + "/armhf/test_arrays"
    p = angr.Project(binary_path)
    cfg = p.analyses.CFGAccurate()

    def check_addr(a):
        if a % 2 == 1:
            nose.tools.assert_true(cfg.is_thumb_addr(a))
        else:
            nose.tools.assert_false(cfg.is_thumb_addr(a))

    # CFGNodes
    cfg_node_addrs = [ n.addr for n in cfg.graph.nodes() ]
    for a in cfg_node_addrs:
        check_addr(a)

    # Functions in function manager
    for f_addr, f in p.kb.functions.items():
        check_addr(f_addr)
        if f.startpoint is not None:
            check_addr(f.startpoint.addr)

def test_fakeret_edges_0():

    # Test the bug where a fakeret edge can be missing in certain cases
    # Reported by Attila Axt (GitHub: @axt)
    # Ref: https://github.com/angr/angr/issues/72

    binary_path = os.path.join(test_location, "x86_64", "cfg_3")

    p = angr.Project(binary_path)
    cfg = p.analyses.CFGAccurate(context_sensitivity_level=3)

    putchar_plt = cfg.functions.function(name="putchar", plt=True)
    nose.tools.assert_true(putchar_plt.returning)

    putchar = cfg.functions.function(name="putchar", plt=False)
    nose.tools.assert_true(putchar.returning)

    # Since context sensitivity is 3, there should be two different putchar nodes
    putchar_cfgnodes = cfg.get_all_nodes(putchar.addr)
    nose.tools.assert_equal(len(putchar_cfgnodes), 2)

    # Each putchar node has a different predecessor as their PLT entry
    plt_entry_0 = cfg.get_predecessors(putchar_cfgnodes[0])
    nose.tools.assert_equal(len(plt_entry_0), 1)
    plt_entry_0 = plt_entry_0[0]

    plt_entry_1 = cfg.get_predecessors(putchar_cfgnodes[1])
    nose.tools.assert_equal(len(plt_entry_1), 1)
    plt_entry_1 = plt_entry_1[0]

    nose.tools.assert_true(plt_entry_0 is not plt_entry_1)

    # Each PLT entry should have a FakeRet edge
    preds_0 = cfg.get_predecessors(plt_entry_0)
    nose.tools.assert_equal(len(preds_0), 1)
    preds_1 = cfg.get_predecessors(plt_entry_1)
    nose.tools.assert_equal(len(preds_1), 1)

    # Each predecessor must have a call edge and a FakeRet edge
    edges_0 = cfg.get_successors_and_jumpkind(preds_0[0], excluding_fakeret=False)
    nose.tools.assert_equal(len(edges_0), 2)
    jumpkinds = set([ jumpkind for _, jumpkind in edges_0 ])
    nose.tools.assert_set_equal(jumpkinds, { 'Ijk_Call', 'Ijk_FakeRet' })

    edges_1 = cfg.get_successors_and_jumpkind(preds_1[0], excluding_fakeret=False)
    nose.tools.assert_equal(len(edges_1), 2)
    jumpkinds = set([ jumpkind for _, jumpkind in edges_1 ])
    nose.tools.assert_set_equal(jumpkinds, { 'Ijk_Call', 'Ijk_FakeRet' })

def test_string_references():

    # Test AttributeError on 'addr' which occurs when searching for string
    # references

    binary_path = os.path.join(test_location, "i386", "ctf_nuclear")
    b = angr.Project(binary_path, load_options={'auto_load_libs': False})
    cfg = b.analyses.CFGAccurate(keep_state=True)

    string_references = []
    for f in cfg.functions.values():
        string_references.append(f.string_references())

    # test passes if hasn't thrown an exception

def test_arrays():

    binary_path = os.path.join(test_location, "armhf", "test_arrays")
    b = angr.Project(binary_path, load_options={'auto_load_libs': False})
    cfg = b.analyses.CFGAccurate()

    node = cfg.get_any_node(0x10415)
    nose.tools.assert_is_not_none(node)

    successors = cfg.get_successors(node)
    nose.tools.assert_equal(len(successors), 2)

def test_max_steps():

    binary_path = os.path.join(test_location, "x86_64", "fauxware")
    b = angr.Project(binary_path, load_options={'auto_load_libs': False})
    cfg = b.analyses.CFGAccurate(max_steps=5)

    dfs_edges = networkx.dfs_edges(cfg.graph)

    depth_map = {}
    for src, dst in dfs_edges:
        if src not in depth_map:
            depth_map[src] = 0
        if dst not in depth_map:
            depth_map[dst] = depth_map[src] + 1
        depth_map[dst] = max(depth_map[src] + 1, depth_map[dst])

    nose.tools.assert_less_equal(max(depth_map.itervalues()), 5)


def test_armel_final_missing_block():

    # Due to a stupid bug in CFGAccurate, the last block of a function might go missing in the function graph if the
    # only entry edge to that block is an Ijk_Ret edge. See #475 on GitHub.
    # Thank @gergo for reporting and providing this test binary.

    binary_path = os.path.join(test_location, 'armel', 'last_block')
    b = angr.Project(binary_path, auto_load_libs=False)
    cfg = b.analyses.CFGAccurate()

    blocks = list(cfg.kb.functions[0x8000].blocks)

    nose.tools.assert_equal(len(blocks), 3)
    nose.tools.assert_set_equal(set([ block.addr for block in blocks ]), { 0x8000, 0x8014, 0x8020 })


def run_all():
    functions = globals()
    all_functions = dict(filter((lambda (k, v): k.startswith('test_')), functions.items()))
    for f in sorted(all_functions.keys()):
        if hasattr(all_functions[f], '__call__'):
            print f
            all_functions[f]()

if __name__ == "__main__":
    logging.getLogger("simuvex.plugins.abstract_memory").setLevel(logging.DEBUG)
    logging.getLogger("angr.surveyors.Explorer").setLevel(logging.DEBUG)
    # logging.getLogger("simuvex.plugins.symbolic_memory").setLevel(logging.DEBUG)
    # logging.getLogger("angr.analyses.cfg_accurate").setLevel(logging.DEBUG)
    # logging.getLogger("s_irsb").setLevel(logging.DEBUG)
    # Temporarily disable the warnings of claripy backend
    #logging.getLogger("claripy.backends.backend").setLevel(logging.ERROR)
    #logging.getLogger("claripy.claripy").setLevel(logging.ERROR)

    import sys
    if len(sys.argv) > 1:
        globals()['test_' + sys.argv[1]]()
    else:
        run_all()
