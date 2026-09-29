// Evaluate rendered admission expressions offline against JSON fixtures.
package main

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/google/cel-go/cel"
	"github.com/google/cel-go/common/types"
)

type Check struct {
	Name        string                 `json:"name"`
	Expressions []string               `json:"expressions"`
	Object      map[string]interface{} `json:"object"`
	OldObject   map[string]interface{} `json:"oldObject"`
	Request     map[string]interface{} `json:"request"`
	Allowed     bool                   `json:"allowed"`
}

func main() {
	var checks []Check
	if err := json.NewDecoder(os.Stdin).Decode(&checks); err != nil {
		panic(err)
	}
	env, err := cel.NewEnv(cel.Variable("object", cel.DynType), cel.Variable("oldObject", cel.DynType), cel.Variable("request", cel.DynType))
	if err != nil {
		panic(err)
	}
	for _, check := range checks {
		allowed := true
		for _, expression := range check.Expressions {
			ast, issues := env.Compile(expression)
			if issues.Err() != nil {
				panic(fmt.Sprintf("%s: %v", check.Name, issues.Err()))
			}
			program, err := env.Program(ast)
			if err != nil {
				panic(err)
			}
			result, _, err := program.Eval(map[string]interface{}{"object": check.Object, "oldObject": check.OldObject, "request": check.Request})
			// An evaluation error is a broken guard, even for a denial fixture.
			if err != nil {
				panic(fmt.Sprintf("%s: %v", check.Name, err))
			}
			if result != types.True {
				allowed = false
			}
		}
		if allowed != check.Allowed {
			panic(fmt.Sprintf("%s: allowed=%v, want %v", check.Name, allowed, check.Allowed))
		}
	}
	fmt.Printf("Admission CEL: %d cases passed\n", len(checks))
}
