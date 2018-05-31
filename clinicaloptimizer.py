# Create IP model and solve calling Cbc solver

from pyomo.environ import *
from pyomo.opt import SolverFactory
import pandas as pd

##############################################################################################################################################
## 
## Relation Algebra on TLINK Temporal Intervals. Defines R1 R2 R3 such that iR1j ^ jR2k => iR3k
## (below to be read from .DAT into Abstract model - see pyomoArcs.dat)
##  p=BEFORE; pi=AFTER; o=OVERLAP; C=CONTAINS; ci=CONTAINS_INV; b=BEGINS_ON; bi=ENDS_ON; n=NONE;

reltypes = ['p', 'pi', 'c', 'ci', 'o', 'b', 'bi', 'n']

maptuple = {'p': 0, 'pi': 1, 'c': 2, 'ci': 3, 'o': 4, 'b': 5, 'bi': 6, 'n': 7}

compositerelations = { 
       
('p','p')   : ('p',), 
('p','pi')  : ('.',), 
('p','c')   : ('p',),
('p','ci')  : ('p','ci','o','bi'),
('p','o')   : ('p','ci','o','bi'),
('p','b')   : ('p','ci','o','bi'),
('p','bi')  : ('p',), 
('p','n')   : ('.',), 
 
('pi','p')  : ('.',), 
('pi','pi') : ('pi',), 
('pi','c')  : ('pi',),
('pi','ci') : ('pi','ci','o','b'),
('pi','o')  : ('pi','ci','o','b'),
('pi','b')  : ('pi','ci','o','b'),
('pi','bi') : ('pi',),
('pi','n')  : ('.',),

('c','p')   : ('p','c','o','bi'), 
('c','pi')  : ('pi','c','o','b'), 
('c','c')   : ('c',),
('c','ci')  : ('c','ci','o'),
('c','o')   : ('c','o'),
('c','b')   : ('c','o'),
('c','bi')  : ('c','o'),
('c','n')   : ('.',),

('ci','p')  : ('p',), 
('ci','pi') : ('pi',), 
('ci','c')  : ('.',),
('ci','ci') : ('ci',),
('ci','o')  : ('p','pi','o','b','bi'), 
('ci','b')  : ('pi',),
('ci','bi') : ('p',),
('ci','n')  : ('.',), 

('o','p')   : ('p','c','o','bi'), 
('o','pi')  : ('pi','c','o','b'), 
('o','c')   : ('c','o'),
('o','ci')  : ('ci','o'),
('o','o')   : ('ci','o','b','bi'), 
('o','b')   : ('pi','c','o'),
('o','bi')  : ('p','c','o'), 
('o','n')   : ('.',), 

('b','p')   : ('p','c','o','bi'),
('b','pi')  : ('pi',), 
('b','c')   : ('pi',),
('b','ci')  : ('ci','o'),
('b','o')   : ('pi','ci','o'),
('b','b')   : ('pi',),
('b','bi')  : ('c','o'), 
('b','n')   : ('.',), 


('bi','p')  : ('p',),
('bi','pi') : ('pi','c','o','b'), 
('bi','c')  : ('p',),
('bi','ci') : ('ci','o'),
('bi','o')  : ('p','ci','o'),
('bi','b')  : ('c','o'),
('bi','bi') : ('p',), 
('bi','n')  : ('.',),

('n','p')   : ('.',), 
('n','pi')  : ('.',), 
('n','c')   : ('.',),
('n','ci')  : ('.',),
('n','o')   : ('.',),
('n','b')   : ('.',),
('n','bi')  : ('.',),
('n','n')   : ('.',)}

###########################################################################################################
#
## Graph functions

# Arcs_init adds arcs to model         
def Arcs_init(df):
    numVars = 0
    retval = []
    for arc, p in df.iterrows() :
        #print("arc: ", arc)
        retval.append(arc)
        numVars += 1
    return retval

# Add connected tri-graphs to model
def Connected_Arcs_init(df):
    retval = []
    for arc1, p in df.iterrows() :
        i = arc1[0]
        ij = arc1[1]
        for arc2, p in df.iterrows() :
            if arc1 != arc2: 
                jk = arc2[0]
                k = arc2[1]
                if ij == jk:
                    ik = (i,k) 
                    if ik in df.index:
                        tuple = ()   
                        tuple += (i,) + (ij,) + (k,) 
                        retval +=(tuple,)
    return retval                 

# Loads 2-d arc/reltype weights into model
def Rels_init(model, left, right, i):
    global df
    index = (left, right)
    return df.loc[index, 'percent'][i]

# Objective function
def Obj_rule(model):
    return summation(model.Rels, model.x)

# Constraint - only one reltype can be assigned per arc
def OnlyOneReltype_rule(model, left, right):
    global numConstraints
    index = (left, right)
    numConstraints += 1
    return sum(model.x[index,i] for i in model.I) == 1

# Constraint - transitive closure rules
def Transitivity_rule(model, i , j, k, arc1IntType, arc2IntType):
    global numConstraints
    arc1 = (i,j)
    arc2 = (j,k)
    arc3 = (i,k)
    arc1RT = model.mapTuple[arc1IntType]
    arc2RT = model.mapTuple[arc2IntType]
    arc3RT = model.compositeRelations[arc1IntType, arc2IntType]
    if arc3RT[0] == '.':
        return Constraint.Feasible
    numConstraints += 1
    return model.x[arc1,arc1RT] + model.x[arc2,arc2RT] - sum(model.x[arc3,model.mapTuple[arc3RT[j]]] for j in range(len(arc3RT))) <=1            

#############################################################################################################    
#
# Optimise Final Classifier using pyomo model
#
#v = {}              # contains dictionary passed from pre-processor
df = pd.DataFrame(columns=('source', 'target', 'percent'))
numConstraints = 0
def main(df_in):
    global df
    global numConstraints
    numConstraints = 0
    df = df_in
    opt = SolverFactory('cbc')
    model = ConcreteModel()
    model.relTypes = Set(initialize=reltypes, ordered=True);
    model.mapTuple = Param(model.relTypes, initialize=maptuple)
    model.compositeRelations = Param (model.relTypes, model.relTypes, initialize=compositerelations) 

    model.I = RangeSet(0, 7)
    model.Arcs = Set(initialize=Arcs_init(df))
    model.Connected_Arcs = Set(initialize=Connected_Arcs_init(df), dimen=3)
    model.Rels = Param(model.Arcs, model.I, initialize=Rels_init)
    model.x = Var(model.Arcs, model.I, domain=Binary)
    model.xProb = Param(model.Arcs, model.I)
    model.Obj = Objective(rule=Obj_rule, sense=maximize)
    model.OnlyOneReltype = Constraint(model.Arcs, rule=OnlyOneReltype_rule) 
    model.Transitivity = Constraint(model.Connected_Arcs, model.relTypes, model.relTypes, rule=Transitivity_rule)
    print("Number of constraints: ", numConstraints)
    
#    print "Optimising model"
    # Create a model instance and optimize
    instance = model.create()
    results = opt.solve(instance)
#    results = opt.solve(instance, tee=True)
#    print results

    # load the results of the optimisation into a dictionary
    instance.load(results)
    row = 0
    df_result = pd.DataFrame(columns=('source', 'target', 'relation'))
    for xVar in instance.active_components(Var):
        varobject = getattr(instance, xVar)
        #rDict = {}
        relTuple = ()
        for index in varobject:
            relTuple += (varobject[index].value,)
            # build the values tuple and
            # add to dictionary when tuple is complete
            if index[2] == len(reltypes) - 1 :
                df_result.loc[row] = [index[0], index[1], relTuple]
                row += 1
                relTuple = ()
    df_result.set_index(['source', 'target'], inplace=True)
    return df_result

if __name__ == "__main__":
    main(sys.argv[1])
