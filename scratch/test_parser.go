package main

import (
	"bufio"
	"fmt"
	"os"
	"regexp"
)

var (
	reIDQ    = regexp.MustCompile(`pdv_idq:\[(\d+)\]`)
	reRef    = regexp.MustCompile(`pdv_referencia:\[(\d+)\]`)
)

func main() {
	path := `C:\Quality\LOG\webPostoPayServer\spring.log`
	file, err := os.Open(path)
	if err != nil {
		fmt.Printf("Error opening file: %v\n", err)
		return
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	count := 0
	found := 0
	for scanner.Scan() {
		line := scanner.Text()
		count++
		if reIDQ.MatchString(line) {
			found++
			if found < 5 {
				fmt.Println("Found match:", line)
			}
		}
	}
	fmt.Printf("Parsed %d lines, found %d matches\n", count, found)
}
