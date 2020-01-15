# Load libraries ----------------------------------------------------------
library(tidyverse)
library(ggplot2)
library(viridis)


# Read CSVs ---------------------------------------------------------------
family_data <- read.csv("../attempt_08/inputs/family_data.csv", stringsAsFactors = FALSE)
accounting_costs <- read.csv("../attempt_07/artifacts/accounting_df.csv", stringsAsFactors = FALSE)
tour_solution <- read.csv("../attempt_08/outputs/tour_solution_68898.csv", stringsAsFactors = FALSE)


# Generate accounting cost heatmap ----------------------------------------
ggplot(accounting_costs, aes(day_0, day_1, fill = log(cost))) +
     geom_tile() +
     scale_fill_viridis_c() +
     theme_minimal(base_size = 12, base_family = "Avenir") +
     theme(panel.border = element_blank(),
           axis.ticks.y = element_blank(),
           axis.text = element_text(color = "black", size = 11),
           plot.title = element_text(face = "bold", size = 16),
           axis.title.x = element_text(margin = margin(20, 0, 10, 0)),
           axis.title.y = element_text(margin = margin(0, 20, 0, 0), angle = 90),
           plot.margin = margin(r = 30, t = 10),
           plot.subtitle = element_text(margin = margin(0, 0, 15, 0)),
           panel.background = element_rect(fill = "transparent", color = NA),
           plot.background = element_rect(fill = "transparent", color = NA),
           legend.background = element_rect(fill = "transparent", color = NA)) +
     xlab("Number of Visitors on Day (d)") +
     ylab("Number of Visitors on Day (d + 1)") +
     ggtitle("Accounting Cost Serves as Load-Balancing Mechanism") +
     labs(subtitle = "Key to Avoid Substantial Differences on Back-to-Back Days",
          fill = "log(Cost)")

ggsave("accounting_cost.png", width = 10, height = 7, units = "in")


# Generate solution stacked bars ------------------------------------------
family_choices <- family_data %>%
     select(-n_people) %>%
     gather(key = "choice", value = "day", -family_id) %>%
     mutate(choice = as.numeric(gsub("^choice_", "", choice)) + 1)

family_members <- family_data %>%
     select(family_id, n_people)

family_solution <- tour_solution %>%
     left_join(family_choices, c("family_id", "assigned_day" = "day")) %>%
     left_join(family_members, "family_id") %>%
     group_by(assigned_day, choice) %>%
     summarize(n_people = sum(n_people)) %>%
     ungroup() %>%
     mutate(choice = factor(choice, levels = 1:5))

family_solution <- rbind(family_solution,
                         data.frame(assigned_day = c(-1, 102),
                                    choice = 1,
                                    n_people = 0,
                                    stringsAsFactors = FALSE))


ggplot(family_solution, aes(fill = choice, y = n_people, x = assigned_day)) +
     geom_bar(position = position_stack(reverse = TRUE), stat = "identity") +
     scale_fill_viridis_d(begin = 0.25) +
     theme_minimal(base_size = 12, base_family = "Avenir") +
     scale_x_continuous(expand = c(0, 0)) +
     scale_y_continuous(expand = c(0, 0), limits = c(0, 325)) +
     theme(panel.border = element_blank(),
           axis.ticks.y = element_blank(),
           axis.text = element_text(color = "black", size = 11),
           axis.title.x = element_text(margin = margin(20, 0, 10, 0)),
           axis.title.y = element_text(margin = margin(0, 20, 0, 0), angle = 90),
           plot.margin = margin(r = 30, t = 10),
           legend.key.size = unit(12, "pt"),
           axis.line.x = element_line(color = "black", size = 0.5),
           panel.background = element_rect(fill = "transparent", color = NA),
           plot.background = element_rect(fill = "transparent", color = NA),
           legend.background = element_rect(fill = "transparent", color = NA),
           panel.grid.major.x = element_blank(),
           panel.grid.minor.x = element_blank()) +
     xlab("Day") +
     ylab("Number of Visitors") +
     labs(fill = "Family Choice") +
     geom_hline(yintercept = 125, linetype = "dashed") +
     geom_hline(yintercept = 300, linetype = "dashed")

ggsave("family_solution.png", width = 12, height = 6, units = "in")



