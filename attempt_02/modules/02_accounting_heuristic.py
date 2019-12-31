# Import libraries ------------------------------------------------
import pandas as pd
import gurobipy as grb
from datetime import datetime
import itertools
import pickle

# Read in dictionaries and recreate arrays ------------------------
family_choices = pickle.load(open("attempt_02/artifacts/family_choices.pkl", "rb"))
preference_cost = pickle.load(open("attempt_02/artifacts/preference_cost.pkl", "rb"))
family_members = pickle.load(open("attempt_02/artifacts/family_members.pkl", "rb"))

family = list(range(0, 5000))
days = list(range(1, 101))

# Initiate model --------------------------------------------------
tour_model = grb.read('attempt_02/artifacts/tour_model.lp')
tour_model.update()

# Read in optimal solution ----------------------------------------
tour_model.read('attempt_02/outputs/tour_initial_solution.sol')
tour_model.update()

# Rebuild visit dictionary ----------------------------------------
all_vars = tour_model.getVars()
visit = {}

for v in all_vars:
    if 'x_' in v.varname:
        var_string = v.varname.replace('x_', '')
        var_split = var_string.split('_')
        f = int(var_split[0])
        d = int(var_split[1])

        visit[f, d] = v

        if v.start > 0.5:
            v.lb = 1
            tour_model.update()

# Remove soft constraints -----------------------------------------
for v in all_vars:
    if 'Soft_' in v.varname:
        tour_model.remove(v)

for c in tour_model.getConstrs():
    if 'Limit_' in c.constrname:
        tour_model.remove(c)

# Define custom penalty function ----------------------------------
def penalty_score(solved_gurobi_model, visit_dictionary, family_dictionary, family_list, day_list):
    preference_penalty = solved_gurobi_model.objVal
    accounting_penalty = 0

    for d in day_list:
        if d == 100:
            today_visitors = grb.quicksum(visit_dictionary[f, d].x * family_dictionary[f]
                                          for f in family_list).getValue()
            tmp_penalty = (today_visitors - 125.0) / 400.0 * today_visitors ** 0.5
        else:
            today_visitors = grb.quicksum(visit_dictionary[f, d].x * family_dictionary[f]
                                          for f in family_list).getValue()
            yesterday_visitors = grb.quicksum(visit_dictionary[f, d + 1].x * family_dictionary[f]
                                              for f in family_list).getValue()
            tmp_penalty = (today_visitors - 125.0) / 400.0 * today_visitors ** \
                          (0.5 + abs(today_visitors - yesterday_visitors) / 50.0)

        accounting_penalty += tmp_penalty

    total_cost = preference_penalty + accounting_penalty

    return int(round(total_cost))


# Set additional model parameter(s) -------------------------------
tour_model.setParam('logtoconsole', 0)
tour_model.update()

# Iterate through model changing visit days -----------------------
tour_model.optimize()
previous_cost = penalty_score(tour_model, visit, family_members, family, days)

output_string = '{:<13{}}{:<10{}}{:<11{}}{:<12{}}{:<11{}}{:<16{}}{:<15{}}{:<{}}'
start_cost = previous_cost
current_cost = previous_cost
start_timestamp = datetime.now()
cost_saved = 0
change_counter = 0
feasible_counter = 0
cost_counter = 0

for i in list(range(1, 51)):
    iter_flag = True
    for a in family:
        for b in family_choices[a]:
            for d in days:
                if visit[a, d].lb == 1:
                    b_prev = d
                    break

            if b_prev != b:
                n_visitors = grb.quicksum(visit[f, b].lb * family_members[f] for f in family).getValue()

                if n_visitors < 300:
                    change_counter += 1

                    visit[a, b_prev].lb = 0
                    visit[a, b].lb = 1
                    tour_model.update()
                    tour_model.optimize()

                    if tour_model.status == grb.GRB.OPTIMAL:
                        feasible_counter += 1

                        tmp_cost = penalty_score(tour_model, visit, family_members, family, days)

                        if tmp_cost < current_cost:
                            cost_counter += 1
                            iter_flag = False
                            current_cost = tmp_cost
                            cost_saved = start_cost - current_cost
                            cumulative_time = (datetime.now() - start_timestamp).total_seconds()

                            if feasible_counter % 10 == 1:
                                print('')
                                print(output_string.format('', 's', '', 's', 'CHANGES', 's',
                                                           'SCHEDULE', 's', 'COST', 's', '', 's',
                                                           '', 's',
                                                           '', '11s'))
                                print(output_string.format('ITERATION', 's', 'FAMILY', 's', 'TESTED', 's',
                                                           'FEASIBLE', 's', 'REDUCED', 's', 'CURRENT COST', 's',
                                                           'TOTAL SAVED', 's',
                                                           'RUN TIME', '11s'))
                                print('-' * 100)

                            print("\033[95m{}\033[00m".format(
                                output_string.format(i, 'd', a, 'd', change_counter, 'd', feasible_counter, 'd',
                                                     cost_counter, 'd', current_cost, ',d',
                                                     cost_saved, ',d', cumulative_time, '11.2f')))

                            tour_model.write('attempt_02/outputs/tour_solution.sol')

                        else:
                            visit[a, b_prev].lb = 1
                            visit[a, b].lb = 0
                            tour_model.update()

                            cumulative_time = (datetime.now() - start_timestamp).total_seconds()

                            if feasible_counter % 10 == 1:
                                print('')
                                print(output_string.format('', 's', '', 's', 'CHANGES', 's',
                                                           'SCHEDULE', 's', 'COST', 's', '', 's',
                                                           '', 's',
                                                           '', '11s'))
                                print(output_string.format('ITERATION', 's', 'FAMILY', 's', 'TESTED', 's',
                                                           'FEASIBLE', 's', 'REDUCED', 's', 'CURRENT COST', 's',
                                                           'TOTAL SAVED', 's',
                                                           'RUN TIME', '11s'))
                                print('-' * 100)

                            print(output_string.format(i, 'd', a, 'd', change_counter, 'd', feasible_counter, 'd',
                                                       cost_counter, 'd', current_cost, ',d',
                                                       cost_saved, ',d', cumulative_time, '11.2f'))
                    else:
                        visit[a, b_prev].lb = 1
                        visit[a, b].lb = 0
                        tour_model.update()

    if iter_flag:
        break

# Rebuild original model and test solution ------------------------
tour_model = grb.read('attempt_02/artifacts/tour_model.lp')
tour_model.update()

tour_model.read('attempt_02/outputs/tour_solution.sol')
all_vars = tour_model.getVars()
for v in all_vars:
    if v.start > 0.5:
        v.lb = 1
tour_model.update()

tour_model.optimize()

if tour_model.status == grb.GRB.OPTIMAL:
    print('')
    print('Model solution is still feasible.')
else:
    print('')
    print('Yikes.')
