# Import libraries ------------------------------------------------
import pandas as pd
import numpy as np
import gurobipy as grb
import itertools
import pickle

# Read CSV --------------------------------------------------------
family_data = pd.read_csv('attempt_02/inputs/family_data.csv')

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
f = open("attempt_02/artifacts/family_choices.pkl", "wb")
pickle.dump(family_choices_dict, f)
f.close()

f = open("attempt_02/artifacts/preference_cost.pkl", "wb")
pickle.dump(preference_cost, f)
f.close()

f = open("attempt_02/artifacts/family_members.pkl", "wb")
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
soft_constraint = {}
absolute_difference_people = 32  # <-- Tune me
soft_constraint_penalty = 18  # <-- Tune me

for d in days:
    constraint = 'Daily_Attendance_GT_%s' % d
    model_constraints[constraint] = tour_model.addConstr(
        grb.quicksum(visit[f, d] * family_members[f] for f in family) >= 125, name=constraint)

    constraint = 'Daily_Attendance_LT_%s' % d
    model_constraints[constraint] = tour_model.addConstr(
        grb.quicksum(visit[f, d] * family_members[f] for f in family) <= 300, name=constraint)

    if d != 100:
        var_name = 'Soft_Constraint_%s' % d
        soft_constraint[d] = tour_model.addVar(obj=soft_constraint_penalty, name=var_name,
                                               vtype=grb.GRB.INTEGER, lb=0, ub=50 - absolute_difference_people)

        constraint = 'Limit_Attendance_Difference_Positive_%s' % d
        model_constraints[constraint] = tour_model.addConstr(
            grb.quicksum(visit[f, d + 1] * family_members[f] for f in family) -
            grb.quicksum(visit[f, d] * family_members[f] for f in family) <=
            absolute_difference_people + soft_constraint[d], name=constraint)

        constraint = 'Limit_Attendance_Difference_Negative_%s' % d
        model_constraints[constraint] = tour_model.addConstr(
            grb.quicksum(visit[f, d + 1] * family_members[f] for f in family) -
            grb.quicksum(visit[f, d] * family_members[f] for f in family) >=
            -1 * absolute_difference_people - soft_constraint[d], name=constraint)

for f in family:
    constraint = 'One_Visit_Per_Family_%s' % f
    model_constraints[constraint] = tour_model.addConstr(
        grb.quicksum(visit[f, d] for d in days) == 1, name=constraint)

tour_model.update()

# Write model to file ---------------------------------------------
tour_model.write('attempt_02/artifacts/tour_model.lp')

# Adjust MIP gap and solve model ----------------------------------
tour_model.setParam('MIPGap', 0.0025)
tour_model.optimize()

# Evaluate total cost ---------------------------------------------
all_vars = tour_model.getVars()
soft_penalty = 0

for v in all_vars:
    if 'Soft_' in v.varname:
        if v.x > 0.5:
            soft_penalty += soft_constraint_penalty * v.x

preference_penalty = tour_model.objVal - soft_penalty

accounting_penalty = 0

for d in days:
    if d == 100:
        today_visitors = grb.quicksum(visit[f, d].x * family_members[f] for f in family).getValue()
        tmp_penalty = (today_visitors - 125.0) / 400.0 * today_visitors ** 0.5
    else:
        today_visitors = grb.quicksum(visit[f, d].x * family_members[f] for f in family).getValue()
        yesterday_visitors = grb.quicksum(visit[f, d + 1].x * family_members[f] for f in family).getValue()
        tmp_penalty = (today_visitors - 125.0) / 400.0 * today_visitors ** \
                      (0.5 + abs(today_visitors - yesterday_visitors) / 50.0)

    accounting_penalty += tmp_penalty

total_cost = preference_penalty + accounting_penalty

print(total_cost)

# Write solution to file ------------------------------------------
tour_model.write('attempt_02/outputs/tour_initial_solution.sol')
