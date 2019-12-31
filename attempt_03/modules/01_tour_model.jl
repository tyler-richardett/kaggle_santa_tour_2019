# Import libraries ------------------------------------------------
using DataFrames, DataFramesMeta, CSV, Ipopt, JuMP, GLPK

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
                     ifelse.(:choice .== "choice_9", 500 .+ 36 .* :n_people,
                         500 .+ 36 .* :n_people .+ 199 .* :n_people)))))))))))

dict_keys = vec([collect(x) for x in Iterators.product([family, days]...)])

preference_cost = Dict(dict_keys .=> family_costs[:cost])
family_members = Dict(family_people[:family_id] .=> family_people[:n_people])

# Initiate model --------------------------------------------------
tour_model = Model(with_optimizer(GLPK.Optimizer))

# Add decision variable -------------------------------------------
visit = Dict()

for f in family
    for d in days
        var_name = string("x_", f, "_", d)
        visit[[f, d]] = @variable(tour_model, base_name = var_name, binary = true)
    end
end

# Set objective ---------------------------------------------------
@objective(tour_model, Min, sum(visit[[f, d]] * preference_cost[[f, d]] for f in family for d in days))

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


optimize!(tour_model)
