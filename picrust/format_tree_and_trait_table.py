#!/usr/bin/env python
# File created on 15 Jul 2011
from __future__ import division

__author__ = "Jesse Zaneveld"
__copyright__ = "Copyright 2011, The PICRUST Project"
__credits__ = ["Jesse Zaneveld"]
__license__ = "GPL"
__version__ = "1.6.0dev"
__maintainer__ = "Jesse Zaneveld"
__email__ = "zaneveld@gmail.com"
__status__ = "Development"

from os.path import splitext
from cogent import LoadTree
from cogent.util.option_parsing import parse_command_line_parameters,\
    make_option

from sys import getrecursionlimit,setrecursionlimit


def reformat_tree_and_trait_table(tree,trait_table_lines,trait_to_tree_mapping,\
    input_trait_table_delimiter="\t", output_trait_table_delimiter="\t",\
    filter_table_by_tree_tips=True, convert_trait_floats_to_ints=False,\
    filter_tree_by_table_entries=True,convert_to_bifurcating=False,\
    add_branch_length_to_root=False, name_unnamed_nodes=True,min_branch_length=0.0001,\
    verbose=True):
    """Return a full reformatted tree,pruned reformatted tree  and set of trait table lines 

    tree - a PyCogent PhyloNode tree object
    
    trait_table_lines -- the lines of a trait table, where 
      the rows are organisms and the columns are traits (e.g. gene counts).
    
    trait_id_to_tree_id_mapping -- a dict keyed by trait table ids, with
      values of tree ids.   If provided, trait table ids will be mapped to 
      tree ids
    
    
    This function combines the various reformatting functions in the 
    library into a catch-all reformatter.  
    """
    
    

    input_tree = tree
    
    #Avoid problems with generators when retreiving specific lines
    if trait_table_lines:
        trait_table_lines = [t.strip() for t in trait_table_lines]
        header_line = trait_table_lines[0]
    else:
        trait_table_lines = []
        header_line = ''

    #replace any spaces in internal node labels with underscores
    for n in input_tree.iterNontips():
        if n.Name:
            n.Name.replace(" ", "_")
        
    #Name unnamed nodes
    if name_unnamed_nodes:
        if verbose:
            print "Naming unnamed nodes in the reference tree...."
        input_tree.nameUnnamedNodes()
    

        
    #map trait table ids to tree ids
    if trait_to_tree_mapping:
        if verbose:
            print "Validating that trait --> tree mappings match tree ids..."
            good,bad = validate_trait_table_to_tree_mappings(input_tree,\
              trait_to_tree_mapping.values(), verbose = True)
            print "Found %i valid ids." %(len(good))
            print "Found %i invalid ids." %(len(bad))
            #if bad:
            #    raise RuntimeError("The following putative tree ids in mapping file aren't actually in the input tree: %s" % bad)
    
    
        if verbose:
            print "Remapping trait table ids to match tree ids...."
        trait_table_lines =\
          remap_trait_table_organisms(trait_table_lines,trait_to_tree_mapping,\
          input_delimiter="\t",output_delimiter="\t",\
          verbose = verbose)
    #Then filter the trait table to include only tree tips
    if filter_table_by_tree_tips:
        if verbose:
            print "Filtering trait table ids to include only those that match tree ids...."
        trait_table_lines = filter_table_by_presence_in_tree(input_tree,\
          trait_table_lines,delimiter=input_trait_table_delimiter)
        
        #if verbose:
        #    print "Verifying that new trait table ids match tree:"
        #    print "# of trait_table_lines: %i" %len(trait_table_lines)
        #    all_tip_ids = [tip.Name for tip in input_tree.iterTips()]
        #    print "example tree tip ids:",all_tip_ids[0:10]
                
    
    #Optionally convert floating point values in the trait table to ints
    if convert_trait_floats_to_ints:
        if verbose:
            print "Converting floating point trait table values to integers...."
        trait_table_lines = convert_trait_values(\
          trait_table_lines,conversion_fn = int,delimiter=input_trait_table_delimiter)
   
    #Write out results
    #output_trait_table_file.writelines(trait_table_lines)
    #trait_table.close()
    #output_trait_table_file.close()
   
    # Use the reformatted trait table to filter tree
    #trait_table = open(output_table_fp,"U")
    #trait_table_lines = trait_table.readlines()

    if filter_tree_by_table_entries:
        if verbose:
            print "filtering tree tips to match entries in trait table...."
        input_tree = filter_tree_tips_by_presence_in_table(input_tree,\
          trait_table_lines,delimiter=input_trait_table_delimiter,\
          verbose=verbose)

    # Tree reformatting

    if convert_to_bifurcating:
        if verbose:
            print "Converting tree to bifurcating...."
        input_tree = input_tree.bifurcating() # Required by most ancSR programs


        input_tree = ensure_root_is_bifurcating(input_tree)
        # The below nutty-looking re-filtering step is necessary
        # When ensuring the root is bifurcating, internal nodes can 
        #get moved to the tips so without additional filtering we 
        #get unannotated tip nodes
        
        if filter_tree_by_table_entries:
            input_tree = filter_tree_tips_by_presence_in_table(input_tree,\
              trait_table_lines,delimiter=input_trait_table_delimiter)

    if min_branch_length:
        if verbose:
            print "Setting a min branch length of %f throughout tree...." \
              % min_branch_length
        input_tree = set_min_branch_length(input_tree,min_length = min_branch_length)

    if add_branch_length_to_root:
        if vebose:
            print "Adding a min branch length of %f to the root node...." \
              % min_branch_length
        input_tree = add_branch_length_to_root(input_tree,root_name=input_tree.Name,\
          root_length=min_branch_length)
    if verbose:
        print "Performing a final round of tree pruning to remove internal nodes with only one child...."
    
    input_tree.prune()
    
    result_trait_table_lines = [header_line]
    result_trait_table_lines.extend(trait_table_lines)
    if verbose:
        print "Final reprocessing of lines..."
    result_trait_table_lines =\
      [line.strip() for line in result_trait_table_lines if line.strip()]
    if verbose:
        print "Done reformatting tree and trait table"
    
    
    return input_tree, result_trait_table_lines


def nexus_lines_from_tree(tree):
    """Return NEXUS formatted lines from a PyCogent PhyloNode tree"""
    lines = ["#NEXUS"]
    lines.extend(make_nexus_trees_block(tree))
    return lines

def add_branch_length_to_root(tree, root_name ="root",root_length=0.0001):
    """Add branch length to the root of a tree if it's shorter than root_length
    tree -- A PyCogent PhyloNode object
    root_name -- the name of the root node
    root_length -- the desired minimum root length
    This is required by some programs such as BayesTraits"""
    
    root = tree.getNodeMatchingName(root_name)
    root.Length = max(root.Length,root_length)
    return tree 
        

def set_min_branch_length(tree,min_length= 0.0001):
    """Return tree modified so that all branchlengths are >= min_length.

    tree -- a PyCogent PhyloNode object"""

    for node in tree.preorder():
        if not node.Parent:
            continue
        node.Length = max(node.Length,min_length)
    return tree


def make_nexus_trees_block(tree):
    """Generate a NEXUS format 'trees' block for a given tree
    
    WARNING:  Removes names from internal nodes, as these cause problems
    downstream
    """

    # First generate the mappings for the NEXUS translate command
    trees_block_template =\
      ["begin trees;",\
      "\ttranslate"]
    name_mappings = {}
    line = None
    for i,node in enumerate(tree.iterTips()):
        name_mappings[node.Name] = i
        if line:
            trees_block_template.append(line)
        
        line = "\t\t%i %s," %(i,node.Name)
    # The last line needs a semicolon rather than a comma
    line = "\t\t%i %s;" %(i,node.Name)
    trees_block_template.append(line)
    
    
    # Reformat tree newick such that names match NEXUS translation table
    for name_to_fix in name_mappings.keys():
        node_to_rename = tree.getNodeMatchingName(name_to_fix)
        node_to_rename.Name=name_mappings[name_to_fix]
    for nonTipNode in tree.iterNontips():
        nonTipNode.Name=''
    

    
    tree_newick = tree.getNewick(with_distances=True)
    #for name_to_fix in name_mappings.keys():
    #    tree_newick = tree_newick.replace(name_to_fix+":",str(name_mappings[name_to_fix])+":")
    #for nonTipNode in tree.iterNontips():
    #    tree_newick = tree_newick.replace(nonTipNode.Name+":","")
    #tree_newick = tree_newick.replace(root_name,"")


    tree_template  = "\t\ttree %s = %s" # tree name then newick string
    line = tree_template % ("PyCogent_tree",tree_newick)
    trees_block_template.append(line)
    
    trees_block_template.append("end;")
    return trees_block_template

def validate_trait_table_to_tree_mappings(tree,trait_table_ids,verbose=True):
    """Report whether tree ids are even in mapping file"""
    good = []
    bad = []
    nodes = [n.Name for n in tree.preorder()]
    for tt_id in trait_table_ids:
        if tt_id in nodes:
            good.append(tt_id)
        else:
            bad.append(tt_id)
    if verbose:
        print "Of %i ids, %i were OK (mapped to tree)" %(len(trait_table_ids),len(good))
        print "Example good ids",good[0:min(len(good),10)]
        print "Example bad ids",bad[0:min(len(bad),10)]
        print "Example node ids",nodes[0:min(len(nodes),10)]
    return good,bad

def filter_table_by_presence_in_tree(tree,trait_table_lines,name_field_index = 0,delimiter="\t"):
    """yield lines of a trait table lacking organisms missing from the tree"""
    #tree_tips = [str(node.Name.strip()) for node in tree.preorder()]
    #print tree_tips
    result_lines = [] 
    for fields in yield_trait_table_fields(trait_table_lines,delimiter):
        curr_name = fields[name_field_index].strip()
        #if curr_name not in tree_tips:
        #    #print curr_name,"could not be found in tree nodes"
        #    print curr_name in tree_tips
        #    try:
        #        print int(curr_name) in tree_tips
        #    except:
        #        pass
        #    print curr_name.strip() in tree_tips
        #    continue
        result_lines.append(delimiter.join(fields)+"\n")
    return result_lines

def convert_trait_values(trait_table_lines,name_field_index=0,delimiter="\t",conversion_fn = int):
    """Convert trait values by running conversion_fn on each"""
    for fields in yield_trait_table_fields(trait_table_lines,delimiter): 
        new_fields = []
        for i,field in enumerate(fields):
            if i != name_field_index:
                new_fields.append(str(conversion_fn(float(field))))
            else:
                new_fields.append(field)
        yield delimiter.join(new_fields).strip()+"\n"





def yield_trait_table_fields(trait_table_lines,delimiter="\t",skip_comment_lines=True,max_field_len=100):
    """Yield fields from trait table lines"""
    for line in trait_table_lines:
        #print "Parsing line:\n",line[0:min(100,len(line))],"..."
        if line.startswith("#") and skip_comment_lines:
            continue
        
        if delimiter not in line:
            delimiters_to_check = {"tab":"\t","space":"","comma":","}
            possible_delimiters = []
            for delim in delimiters_to_check.keys():
                if delimiters_to_check[delim] in line:
                    possible_delimiters.append(delim)
            error_line = "Delimiter '%s' not in line.  The following delimiters were found:  %s.  Is the correct delimiter one of these?"
            raise RuntimeError(error_line % (delimiter,",".join(possible_delimiters)))
                     
        fields = line.split(delimiter)
        yield fields



def ensure_root_is_bifurcating(tree,root_name='root',verbose=False):
    """Remove child node of root if it is a single child"""
    root_node = tree.getNodeMatchingName(root_name)
    if len(root_node.Children) == 1:
        if verbose:
            print "Rerooting to avoid monotomy at root"
        tree = tree.rootedAt(root_node.Children[0].Name)
        #tree.remove(root_node)
    tree.prune()

    return tree

def filter_tree_tips_by_presence_in_table(tree,trait_table_lines,name_field_index = 0,\
      delimiter="\t",verbose=True):
    """yield a tree lacking organisms missing from the trait table"""
    org_ids_in_trait_table = []
    new_tree = tree.deepcopy()
    
    for fields in yield_trait_table_fields(trait_table_lines, delimiter):
        curr_org = fields[name_field_index].strip()
        org_ids_in_trait_table.append(curr_org)
    

    # Build up a list of tips to prune
    tips_to_prune = []
    tips_not_to_prune = []
    n_tips_not_to_prune = 0
    for tip in tree.iterTips():
        if tip.Name.strip() not in org_ids_in_trait_table:
            tips_to_prune.append(tip.Name)
            #if verbose:
            #    print "Tree tip name:",tip.Name
            #    print "Example org ids:",org_ids_in_trait_table[0:10]
        else:
            n_tips_not_to_prune += 1
            tips_not_to_prune.append(tip.Name)

    if not n_tips_not_to_prune:
        raise RuntimeError(\
          "filter_tree_tips_by_presence_in_table:  operation would remove all tips.  Is this due to a formatting error in inputs?")
    if verbose: 
        print "%i of %i tips will be pruned (leaving %i)" %(len(tips_to_prune),\
          n_tips_not_to_prune + len(tips_to_prune), n_tips_not_to_prune)
        print "Example tips that will be pruned (first 10):\n\n%s" % \
          tips_to_prune[0:min(len(tips_to_prune),10)]
    #TODO: This step seems to be super slow
    #for i,tip_name in enumerate(tips_to_prune):
    #    
    #    tip = new_tree.getNodeMatchingName(tip_name)
    #    if tip.Parent is not None:
    #        if verbose:
    #            print 'removing tip  %i/%i' %(i,len(tips_to_prune))
    #        removal_ok = tip.Parent.remove(tip)
    #    else:
    #        removal_ok = False
    #if verbose:
    #    print 'pruning....' 
    #new_tree.prune()
    try: 
        new_tree = new_tree.getSubTree(tips_not_to_prune)
    except RuntimeError:
        #NOTE:  getSubTree will hit 
        #maximum recursion depth on large trees
        #Try working around this issue with a large
        #recursion depth limit
        old_recursion_limit = getrecursionlimit()
        setrecursionlimit(50000)
        new_tree = new_tree.getSubTree(tips_not_to_prune)
        setrecursionlimit(old_recursion_limit)
    return new_tree

def print_node_summary_table(input_tree):
    """Print a summary of the name,children,length, and parents of each node"""
    for node in input_tree.postorder():
        if node.Parent:
            parent_name = node.Parent.Name
        else:
            parent_name = None
        yield "\t".join(map(str,[node.Name,len(node.Children),node.Length,parent_name]))
 

def add_to_filename(filename,new_suffix,delimiter="_"):
    """Add to a filename, preserving the extension"""
    filename, ext = splitext(filename)
    new_filename = delimiter.join([filename,new_suffix])
    return "".join([new_filename,ext])
 

def make_id_mapping_dict(tree_to_trait_mappings):
    """Generates trait_to_tree mapping dictionary from a list of mapping tuples

    mappings -- in the format tree_id, trait_id
    
    """
    trait_to_tree_mapping_dict = {}
    tree_to_trait_mapping_dict = {}
    
    for tree_id,trait_id in tree_to_trait_mappings:
        trait_to_tree_mapping_dict[trait_id] = tree_id
        tree_to_trait_mapping_dict[tree_id] = trait_id

    return trait_to_tree_mapping_dict

def parse_id_mapping_file(file_lines,delimiter="\t"):
    """Parse two-column id mapping file, returning a generator of fields"""
    for line in file_lines:
        yield line.strip().split(delimiter)


def remap_trait_table_organisms(trait_table_lines,trait_to_tree_mapping_dict,\
  input_delimiter="\t",output_delimiter="\t",verbose=False):
    """Yield trait table lines with organism ids substituted using the mapping dict
    
    trait_table_lines -- tab-delimited lines of organism\tcounts (each count gets
      a column).   

    """
 
    remapped_lines = []
    bad_ids = []
    default_total = 0
    #if verbose:
    #    print trait_to_tree_mapping_dict
    #    print sorted(list(set(trait_to_tree_mapping_dict.keys())))
    for i,line in enumerate(trait_table_lines):
        #if verbose:
        #    print i,line

        if line.startswith("#") or line.startswith("GenomeID"):
            continue 
        fields = line.strip().split(input_delimiter)
        #if verbose:
        #    print fields
            
        if verbose:
            old_id = fields[0]
        try:
            fields[0] = trait_to_tree_mapping_dict[fields[0]]
        except KeyError:
            bad_ids.append(fields[0])
            continue
        #fields[0] = trait_to_tree_mapping_dict[fields[0]]
        result =  output_delimiter.join(fields)+"\n" 
        
        remapped_lines.append(result)

    if verbose and bad_ids:
        print "%i of %i trait table ids could not be mapped to tree" %(len(bad_ids),len(remapped_lines))
        print "Example trait table ids that could not be mapped to tree:" %(bad_ids[:min(len(bad_ids),10)])
    return remapped_lines
