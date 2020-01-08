# Import libraries ------------------------------------------------
using DataFrames, DataFramesMeta, CSV, Ipopt, Juniper, JuMP

# Read CSV --------------------------------------------------------
family_data = CSV.read("family_data.csv")

# Define indices and data -----------------------------------------
family = 0:4999
days = 1:100

family_days = DataFrame(Iterators.product(days, family))
family_days = @linq family_days |> select(family_id = :2, day = :1)

family_people = @linq family_data |> select(:family_id, :n_people)

family_choices = melt(family_data, :family_id)
family_choices = @linq family_choices |>
    select(:family_id, choice = :variable, day = :value) |>
    transform(choice = string.(:choice)) |>
    where(:choice .!= "n_people")

family_costs = join(family_days, family_choices,
                    on = [:family_id, :day], kind = :left)
family_costs = join(family_costs, family_people, on = :family_id, kind = :left)

family_costs = @linq family_costs |>
    transform(choice = ifelse.(ismissing.(:choice), "none", :choice)) |>
    transform(cost = ifelse.(:choice .== "choice_0", 0,
                     ifelse.(:choice .== "choice_1", 50,
                     ifelse.(:choice .== "choice_2", 50 .+ 9 .* :n_people,
                     ifelse.(:choice .== "choice_3", 100 .+ 9 .* :n_people,
                     ifelse.(:choice .== "choice_4", 200 .+ 9 .* :n_people,
                     ifelse.(:choice .== "choice_5", 200 .+ 18 .* :n_people,
                     ifelse.(:choice .== "choice_6", 300 .+ 18 .* :n_people,
                     ifelse.(:choice .== "choice_7", 300 .+ 36 .* :n_people,
                     ifelse.(:choice .== "choice_8", 400 .+ 36 .* :n_people,
                     ifelse.(:choice .== "choice_9", 500 .+ 36 .* :n_people .+ 199 .* :n_people,
                         500 .+ 36 .* :n_people .+ 398 .* :n_people)))))))))))

dict_keys = vec([collect(x) for x in Iterators.product([days, family]...)])

preference_cost = Dict(dict_keys .=> family_costs[:cost])
family_members = Dict(family_people[:family_id] .=> family_people[:n_people])

# Initiate model --------------------------------------------------
optimizer = Juniper.Optimizer
params = Dict{Symbol,Any}()
params[:nl_solver] = with_optimizer(Ipopt.Optimizer, print_level = 6)

tour_model = Model(with_optimizer(optimizer, params))

# Add decision variable -------------------------------------------
visit = Dict()

for f in family
    for d in days
        var_name = string("x_", f, "_", d)
        visit[[f, d]] = @variable(tour_model, base_name = var_name, binary = true)
    end
end

# Set objective ---------------------------------------------------
@NLobjective(tour_model, Min,
    sum(visit[[f, d]] * preference_cost[[d, f]] for f in family, d in days) +
    sum((sum(visit[[f, d]] * family_members[f] for f in family) - 125) / 400 *
        (sum(visit[[f, d]] * family_members[f] for f in family))^(0.5 + abs(sum(visit[[f, d]] * family_members[f] for f in family) - sum(visit[[f, d + 1]] * family_members[f] for f in family)) / 50.0)
        for d in days if d != 100) +
    ((sum(visit[[f, 100]] * family_members[f] for f in family) - 125) / 400 *
        (sum(visit[[f, 100]] * family_members[f] for f in family))^0.5))

# Set constraints -------------------------------------------------
model_constraints = Dict()

for d in days
    constraint = string("Daily_Attendance_GT_", d)
    model_constraints[constraint] = @constraint(tour_model, sum(visit[[f, d]] * family_members[f] for f in family) .>= 125, base_name = constraint)

    constraint = string("Daily_Attendance_LT_", d)
    model_constraints[constraint] = @constraint(tour_model, sum(visit[[f, d]] * family_members[f] for f in family) .<= 300, base_name = constraint)
end

for f in family
    constraint = string("One_Visit_Per_Family_", f)
    model_constraints[constraint] = @constraint(tour_model, sum(visit[[f, d]] for d in days) .== 1, base_name = constraint)
end

# Write model to file ---------------------------------------------
f = open("tour_model.lp", "w")
print(f, tour_model)
close(f)

# Solve model -----------------------------------------------------
optimize!(tour_model)
