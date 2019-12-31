# Import libraries ------------------------------------------------
import pandas as pd
import numpy as np
import gurobipy as grb
import itertools
import pickle

# Read CSV --------------------------------------------------------
family_data = pd.read_csv('attempt_01/inputs/family_data.csv')

# Define indices and data -----------------------------------------
family = list(range(0, 5000))
days = list(range(1, 101))

family_days = pd.DataFrame(list(itertools.product(family, days)), columns=['family_id', 'day'])
family_people = family_data[['family_id', 'n_people']]
family_choices = pd.wide_to_long(family_data, stubnames='choice_', i='family_id', j='day') \
    .reset_index() \
    .rename(columns={'day': 'choice', 'choice_': 'day'}) \
    .drop('n_people', axis=1)

family_costs = family_days \
    .merge(family_choices, how='left', on=['family_id', 'day']) \
    .merge(family_people, how='left', on='family_id')

conditions = [(family_costs['choice'] == 0), (family_costs['choice'] == 1), (family_costs['choice'] == 2),
              (family_costs['choice'] == 3), (family_costs['choice'] == 4), (family_costs['choice'] == 5),
              (family_costs['choice'] == 6), (family_costs['choice'] == 7), (family_costs['choice'] == 8),
              (family_costs['choice'] == 9)]
choices = [0,
           50,
           50 + 9 * family_costs['n_people'],
           100 + 9 * family_costs['n_people'],
           200 + 9 * family_costs['n_people'],
           200 + 18 * family_costs['n_people'],
           300 + 18 * family_costs['n_people'],
           300 + 36 * family_costs['n_people'],
           400 + 36 * family_costs['n_people'],
           500 + 36 * family_costs['n_people'] + 199 * family_costs['n_people']]

family_costs['cost'] = np.select(conditions, choices,
                                 default=500 + 36 * family_costs['n_people'] + 398 * family_costs['n_people'])

family_choices_dict = family_choices \
    .sort_values(['family_id', 'choice']) \
    .drop('choice', axis=1) \
    .groupby('family_id')['day'] \
    .apply(list) \
    .to_dict()

preference_cost = family_costs \
    .set_index(['family_id', 'day'])['cost'] \
    .to_dict()

family_members = family_people \
    .set_index('family_id')['n_people'] \
    .to_dict()

# Write dictionaries to pickle for later --------------------------
f = open("attempt_01/artifacts/family_choices.pkl", "wb")
pickle.dump(family_choices_dict, f)
f.close()

f = open("attempt_01/artifacts/preference_cost.pkl", "wb")
pickle.dump(preference_cost, f)
f.close()

f = open("attempt_01/artifacts/family_members.pkl", "wb")
pickle.dump(family_members, f)
f.close()

# Initiate model --------------------------------------------------
tour_model = grb.Model()

# Add decision variable -------------------------------------------
visit = {}

for f in family:
    for d in days:
        var_name = 'x_%s_%s' % (f, d)
        visit[f, d] = tour_model.addVar(name=var_name, vtype=grb.GRB.BINARY)

tour_model.update()

# Set objective ---------------------------------------------------
tour_model.setObjective(grb.quicksum(visit[f, d] * preference_cost[f, d] for f in family for d in days),
                        sense=grb.GRB.MINIMIZE)

tour_model.update()

# Set constraints -------------------------------------------------
model_constraints = {}

for d in days:
    constraint = 'Daily_Attendance_GT_%s' % d
    model_constraints[constraint] = tour_model.addConstr(
        grb.quicksum(visit[f, d] * family_members[f] for f in family) >= 125, name=constraint)

    constraint = 'Daily_Attendance_LT_%s' % d
    model_constraints[constraint] = tour_model.addConstr(
        grb.quicksum(visit[f, d] * family_members[f] for f in family) <= 300, name=constraint)

for f in family:
    constraint = 'One_Visit_Per_Family_%s' % f
    model_constraints[constraint] = tour_model.addConstr(
        grb.quicksum(visit[f, d] for d in days) == 1, name=constraint)

tour_model.update()

# Write model to file ---------------------------------------------
tour_model.write('attempt_01/artifacts/tour_model.lp')

# Solve initial model and write to file ---------------------------
tour_model.optimize()
tour_model.write('attempt_01/outputs/tour_initial_solution.sol')
