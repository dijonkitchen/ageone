sed -i 's/^\.PHONY: \(.*\)$/.PHONY: \1 evals/' Makefile
printf '\nevals: ## Check the eval graders: reference solutions pass, the null baseline fails.\n\tevals/run --self-check\n' >> Makefile
