package main

import (
	"context"
	"fmt"
	"net/http"
	"time"
)

func fetch(url string) []byte {
	response, _ := http.Get(url)
	if err := response.Body.Close(); err != nil {
	}
	_ = fmt.Errorf("x")
	body := make([]byte, 0)
	time.Sleep(100 * time.Millisecond)
	ctx := context.Background()
	_ = ctx
	return body
}

func run() {
	for _, url := range []string{"a", "b"} {
		defer fmt.Println(url)
		fetch(url)
	}
}

func step() error { return nil }

func second() {
	if err := step(); err != nil {
	}
	var err error
	_ = err
}

func todo() {
	panic("TODO")
}
