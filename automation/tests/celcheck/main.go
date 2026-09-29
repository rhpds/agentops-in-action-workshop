// Evaluate rendered admission expressions offline against JSON fixtures.
package main

import (
	_ "embed"
	"encoding/json"
	"fmt"
	apiservercel "k8s.io/apiserver/pkg/cel"
	"k8s.io/apiserver/pkg/cel/openapi"
	"k8s.io/kube-openapi/pkg/validation/spec"
	"os"
	"strings"

	"github.com/google/cel-go/cel"
	"github.com/google/cel-go/common/types"
)

//go:embed application-schema.json
var applicationSchema []byte

func applicationEnv() *cel.Env {
	var schema spec.Schema
	if err := json.Unmarshal(applicationSchema, &schema); err != nil {
		panic(err)
	}
	decl := openapi.SchemaDeclType(&schema, false).MaybeAssignTypeName("Application")
	// ObjectMeta is supplied by Kubernetes, not described by the CRD.
	decl.Fields["metadata"] = apiservercel.NewDeclField("metadata", apiservercel.DynType, true, nil, nil)
	base, err := cel.NewEnv()
	if err != nil {
		panic(err)
	}
	opts, err := apiservercel.NewDeclTypeProvider(decl).EnvOptions(base.TypeProvider())
	if err != nil {
		panic(err)
	}
	opts = append(opts, cel.Variable("object", decl.CelType()), cel.Variable("oldObject", decl.CelType()), cel.Variable("request", cel.DynType))
	env, err := base.Extend(opts...)
	if err != nil {
		panic(err)
	}
	return env
}

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
	typed := applicationEnv()
	// This must fail: dynamic-only checking previously missed this production bug.
	if _, issues := typed.Compile("object.spec.all(k, true)"); issues.Err() == nil {
		panic("Application schema was not enforced")
	}
	for _, check := range checks {
		allowed := true
		for _, expression := range check.Expressions {
			if check.Object["kind"] == "Application" {
				if _, issues := typed.Compile(expression); issues.Err() != nil {
					panic(fmt.Sprintf("%s (typed): %v", check.Name, issues.Err()))
				}
			}
			// Kubernetes escapes reserved schema field names; plain JSON maps do not.
			ast, issues := env.Compile(strings.ReplaceAll(expression, ".__namespace__", ".namespace"))
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
