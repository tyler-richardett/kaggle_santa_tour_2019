# Import libraries ------------------------------------------------
import pandas as pd
import numpy as np
import gurobipy as grb
import itertools
import pickle
import math

# Read CSV --------------------------------------------------------
family_data = pd.read_csv('attempt_07/inputs/family_data.csv')

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

attendance_range = list(range(125, 301))

accounting_df = pd.DataFrame(list(itertools.product(attendance_range, attendance_range)),
                             columns=['day_0', 'day_1'])
accounting_df['cost'] = (accounting_df['day_0'] - 125.0) / 400.0 * \
                        accounting_df['day_0']**(0.5 + abs(accounting_df['day_0'] - accounting_df['day_1']) / 50.0)

accounting_cost = accounting_df \
    .set_index(['day_0', 'day_1'])['cost'] \
    .to_dict()

attendance_self = accounting_df \
    .query('day_0 == day_1') \
    .set_index('day_0')['day_1'] \
    .to_dict()

# Write dictionaries to pickle for later --------------------------
f = open("attempt_07/artifacts/family_choices.pkl", "wb")
pickle.dump(family_choices_dict, f)
f.close()

f = open("attempt_07/artifacts/preference_cost.pkl", "wb")
pickle.dump(preference_cost, f)
f.close()

f = open("attempt_07/artifacts/accounting_cost.pkl", "wb")
pickle.dump(accounting_cost, f)
f.close()

f = open("attempt_07/artifacts/family_members.pkl", "wb")
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

attendance = {}

for d in days:
    var_name = 'attendance_%s' % d
    attendance[d] = tour_model.addVar(name=var_name, vtype=grb.GRB.INTEGER, lb=125, ub=300)

accounting = {}

for d in days:
    for a in attendance_range:
        for b in attendance_range:
            var_name = 'accounting_%s_%s_%s' % (d, a, b)
            accounting[d, a, b] = tour_model.addVar(name=var_name, vtype=grb.GRB.BINARY)

tour_model.update()

# Set objective ---------------------------------------------------
tour_model.setObjective(grb.quicksum(visit[f, d] * preference_cost[f, d] for f in family for d in days) +
                        grb.quicksum(accounting[d, a, b] * accounting_cost[a, b]
                                     for d in days for a in attendance_range for b in attendance_range),
                        sense=grb.GRB.MINIMIZE)

tour_model.update()

# Set constraints -------------------------------------------------
model_constraints = {}

for d in days:
    constraint = 'Set_Attendance_%s' % d
    model_constraints[constraint] = tour_model.addConstr(
        grb.quicksum(visit[f, d] * family_members[f] for f in family) == attendance[d], name=constraint
    )

    constraint = 'Force_Accounting_Attendance_Today_%s' % d
    model_constraints[constraint] = tour_model.addConstr(
        grb.quicksum(accounting[d, a, b] * attendance_self[a] for a in attendance_range
                     for b in attendance_range) == attendance[d], name=constraint
    )

    if d != 100:
        for w in attendance_range:
            constraint = 'Force_Accounting_Attendance_Equality_%s_%s' % (d, w)
            model_constraints[constraint] = tour_model.addConstr(
                grb.quicksum(accounting[d, a, w] for a in attendance_range) ==
                grb.quicksum(accounting[d + 1, w, b] for b in attendance_range)
            )

        constraint = 'Force_Accounting_Attendance_Yesterday_%s' % d
        model_constraints[constraint] = tour_model.addConstr(
            grb.quicksum(accounting[d, a, b] * attendance_self[b] for a in attendance_range
                         for b in attendance_range) == attendance[d + 1], name=constraint
        )
    else:
        constraint = 'Force_Accounting_Attendance_Yesterday_%s' % d
        model_constraints[constraint] = tour_model.addConstr(
            grb.quicksum(accounting[d, a, b] * attendance_self[b] for a in attendance_range
                         for b in attendance_range) == attendance[d], name=constraint
        )

    constraint = 'One_Accounting_Variable_Per_Day_%s' % d
    model_constraints[constraint] = tour_model.addConstr(
        grb.quicksum(accounting[d, a, b] for a in attendance_range for b in attendance_range) == 1, name=constraint
    )

for f in family:
    constraint = 'One_Visit_Per_Family_%s' % f
    model_constraints[constraint] = tour_model.addConstr(
        grb.quicksum(visit[f, d] for d in days) == 1, name=constraint)

tour_model.update()

# Write model to file ---------------------------------------------
tour_model.write('attempt_07/artifacts/tour_model.lp')

# Set parameters --------------------------------------------------
tour_model.setParam('MIPFocus', 3)
tour_model.setParam('Cuts', 0)
tour_model.setParam('Cutoff', 68888.05)

# Solve model -----------------------------------------------------
tour_model.optimize()

# Write solution to file ------------------------------------------
tour_model.write('attempt_07/outputs/tour_solution.sol')

# Extract solution for Kaggle -------------------------------------
solution = pd.DataFrame()
solution_vars = tour_model.getVars()

for v in solution_vars:
    if 'x_' in v.varname:
        if v.x > 0.5:
            var_string = v.varname
            var_split = var_string.split('_')
            f = var_split[1]
            d = var_split[2]

            tmp_solution = pd.DataFrame({'family_id': [int(f)], 'assigned_day': [int(d)]})
            solution = solution.append(tmp_solution)

solution = solution.sort_values('family_id')
solution.to_csv('attempt_07/outputs/tour_solution_%d.csv' % math.floor(tour_model.objVal), index=False)
