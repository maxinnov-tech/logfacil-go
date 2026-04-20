package parser

import (
	"unicode/utf8"

	"golang.org/x/text/encoding"
	"golang.org/x/text/encoding/charmap"
	"golang.org/x/text/transform"
)

// DecodeToUTF8 converte bytes para string UTF-8 válida seguindo a mesma
// ordem de prioridade do Python: ENCODINGS = ("cp1252", "latin-1", "utf-8")
//
//   - Se já for UTF-8 válido → retorna direto (zero-copy, caso mais comum).
//   - Se não for UTF-8 → tenta Windows-1252 (padrão Windows Brasil: acentos ã, ç, ê...).
//   - Se falhar → latin-1 (ISO-8859-1), que nunca falha (cobre todos os 256 bytes).
//   - Último recurso: substitui bytes inválidos por '?' (Python errors="replace").
func DecodeToUTF8(raw []byte) string {
	// Passo 1: Já é UTF-8 válido? Retorna direto.
	if utf8.Valid(raw) {
		return string(raw)
	}

	// Passo 2: cp1252 (Windows-1252) — primeiro da lista ENCODINGS do Python.
	if decoded, ok := tryDecode(raw, charmap.Windows1252); ok {
		return decoded
	}

	// Passo 3: latin-1 (ISO-8859-1) — segundo da lista ENCODINGS do Python. Nunca falha.
	if decoded, ok := tryDecode(raw, charmap.ISO8859_1); ok {
		return decoded
	}

	// Último recurso: substitui bytes inválidos de UTF-8 por '?' (Python errors="replace")
	return replaceInvalidUTF8(raw)
}

// tryDecode tenta decodificar bytes usando a codificação especificada.
func tryDecode(data []byte, enc encoding.Encoding) (string, bool) {
	result, _, err := transform.Bytes(enc.NewDecoder(), data)
	if err != nil {
		return "", false
	}
	return string(result), true
}

// replaceInvalidUTF8 substitui sequências de bytes inválidas de UTF-8 por '?'.
func replaceInvalidUTF8(data []byte) string {
	buf := make([]byte, 0, len(data))
	for i := 0; i < len(data); {
		r, size := utf8.DecodeRune(data[i:])
		if r == utf8.RuneError && size == 1 {
			buf = append(buf, '?')
			i++
		} else {
			buf = append(buf, data[i:i+size]...)
			i += size
		}
	}
	return string(buf)
}
