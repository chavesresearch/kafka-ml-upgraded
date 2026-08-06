// A real Monaco language definition for Berry (https://github.com/berry-lang/berry),
// the scripting language Tasmota firmware actually runs - CodeEditor used to
// highlight this field as Lua, "closest built-in grammar", which is wrong:
// Berry's comments (`#`/`#- -#`), block-closing keyword (`end`, not
// `then`/`do`/`function`'s own terminators), and keyword set all differ from
// Lua's. Monaco has no built-in Berry grammar, so this is hand-written
// against Berry's own authoritative sources rather than guessed - the
// project's official Pygments lexer (tools/highlighters/Pygments/berry.py)
// for the exact keyword/builtin/operator/string/comment token classes, and
// its EBNF grammar (tools/grammar/berry.ebnf) for the full operator set
// (walrus `:=`, range `..`, arrow `->` for lambdas, compound assignment
// operators) - see https://github.com/berry-lang/berry/tree/master/tools.
import type * as Monaco from 'monaco-editor/esm/vs/editor/editor.api'

export const berryLanguageConfiguration: Monaco.languages.LanguageConfiguration = {
  comments: {
    lineComment: '#',
    blockComment: ['#-', '-#'],
  },
  brackets: [
    ['{', '}'],
    ['[', ']'],
    ['(', ')'],
  ],
  autoClosingPairs: [
    { open: '{', close: '}' },
    { open: '[', close: ']' },
    { open: '(', close: ')' },
    { open: '"', close: '"' },
    { open: "'", close: "'" },
  ],
  surroundingPairs: [
    { open: '{', close: '}' },
    { open: '[', close: ']' },
    { open: '(', close: ')' },
    { open: '"', close: '"' },
    { open: "'", close: "'" },
  ],
}

export const berryLanguageDefinition: Monaco.languages.IMonarchLanguage = {
  defaultToken: '',
  tokenPostfix: '.berry',

  // 'as', 'import', 'static', 'self', 'super' + true/false/nil + var/def
  // (Pygments 'keywords' state) and if/elif/else/for/while/do/end/break/
  // continue/return/try/except/raise (Pygments 'controls' state) + class
  // (EBNF class_stmt, not in the Pygments file at all - a real gap in the
  // upstream lexer, confirmed by cross-checking the EBNF).
  keywords: [
    'as', 'break', 'class', 'continue', 'def', 'do', 'elif', 'else', 'end',
    'except', 'false', 'for', 'if', 'import', 'nil', 'raise', 'return',
    'self', 'static', 'super', 'true', 'try', 'var', 'while',
  ],

  // Pygments 'builtins' state - real functions/classes always available in
  // the global namespace, not reserved words (a Berry script can still
  // shadow them), so they get their own token class rather than 'keyword'.
  builtins: [
    'assert', 'bool', 'bytes', 'call', 'classname', 'classof', 'compile',
    'file', 'input', 'int', 'isinstance', 'issubclass', 'list', 'map',
    'module', 'number', 'open', 'print', 'range', 'real', 'size', 'str',
    'type',
  ],

  operators: [
    '=', '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^=', '<<=', '>>=',
    '==', '!=', '<=', '>=', '<', '>', '&&', '||', '<<', '>>', '&', '|', '^',
    '+', '-', '*', '/', '%', '..', '?', ':', '->', ':=', '~', '!',
  ],

  // Includes '.' (unlike Monaco's own built-in Lua grammar) specifically so
  // the range operator '..' groups into one token instead of two lone dots -
  // the EBNF calls this out as its own production (range_expr), not just
  // punctuation.
  symbols: /[=><!~?:&|+\-*/^%.]+/,
  escapes: /\\(?:[abfnrtv\\"']|x[0-9A-Fa-f]{1,2}|u[0-9A-Fa-f]{4})/,

  tokenizer: {
    root: [
      // f-strings (EBNF: f_string = 'f' STRING) - the leading f is part of
      // the string, not a separate identifier; matched via lookahead so it
      // doesn't consume the quote itself, which the @string state below
      // still needs to see.
      [/f(?=["'])/, 'string.quote'],

      [/[a-zA-Z_]\w*/, {
        cases: {
          '@keywords': 'keyword',
          '@builtins': 'predefined',
          '@default': 'identifier',
        },
      }],

      { include: '@whitespace' },

      [/[{}()[\]]/, '@brackets'],
      [/@symbols/, {
        cases: {
          '@operators': 'delimiter',
          '@default': '',
        },
      }],

      // numbers (EBNF INTEGER/REAL, Pygments 'numbers' state)
      [/\d*\.\d+([eE][-+]?\d+)?/, 'number.float'],
      [/0[xX][0-9a-fA-F]+/, 'number.hex'],
      [/\d+/, 'number'],

      [/[;,]/, 'delimiter'],

      // strings: recover on non-terminated strings, same convention Monaco's
      // own basic-language grammars use.
      [/"([^"\\]|\\.)*$/, 'string.invalid'],
      [/'([^'\\]|\\.)*$/, 'string.invalid'],
      [/"/, 'string', '@string."'],
      [/'/, 'string', "@string.'"],
    ],

    whitespace: [
      [/[ \t\r\n]+/, ''],
      // Pygments: r'#-(.|\n)*?-#' (multiline block) vs r'#(\n|[\w\W]*?\n)'
      // (single line, to end of line) - '#-' must be checked first or it'd
      // never be reached (a bare '#' rule would swallow it as a line comment).
      [/#-/, 'comment', '@blockComment'],
      [/#.*$/, 'comment'],
    ],

    // No nesting in Berry's own grammar (unlike Lua's balanced [=[ ]=] block
    // comments) - a plain "consume until the literal -# close" state machine.
    blockComment: [
      [/[^-]+/, 'comment'],
      [/-#/, 'comment', '@pop'],
      [/-/, 'comment'],
    ],

    string: [
      [/[^\\"']+/, 'string'],
      [/@escapes/, 'string.escape'],
      [/\\./, 'string.escape.invalid'],
      [/["']/, {
        cases: {
          '$#==$S2': { token: 'string', next: '@pop' },
          '@default': 'string',
        },
      }],
    ],
  },
}
