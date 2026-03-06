#!/usr/bin/env node
import fs from 'fs';
import { resolve, dirname } from 'path';
import color from 'cli-color';
import sade from 'sade';
import glob from 'tiny-glob';
import { parse, preprocess } from 'svelte/compiler';
import { walk } from 'estree-walker';

const isNumberString = (n) => !Number.isNaN(parseInt(n, 10));
function deepSet(obj, path, value) {
  const parts = path.replace(/\[(\w+)\]/gi, ".$1").split(".");
  return parts.reduce((ref, part, i) => {
    if (part in ref)
      return ref = ref[part];
    if (i < parts.length - 1) {
      if (isNumberString(parts[i + 1])) {
        return ref = ref[part] = [];
      }
      return ref = ref[part] = {};
    }
    return ref[part] = value;
  }, obj);
}

function getObjFromExpression(exprNode) {
  return exprNode.properties.reduce((acc, prop) => {
    if (prop.type === "SpreadElement")
      return acc;
    if (prop.value.type === "Literal" && prop.value.value !== Object(prop.value.value)) {
      const key = prop.key.name;
      acc[key] = prop.value.value;
    }
    return acc;
  }, {});
}

function delve(obj, fullKey) {
  if (fullKey == null)
    return void 0;
  if (fullKey in obj) {
    return obj[fullKey];
  }
  const keys = fullKey.split(".");
  let result = obj;
  for (let p = 0; p < keys.length; p++) {
    if (typeof result === "object") {
      if (p > 0) {
        const partialKey = keys.slice(p, keys.length).join(".");
        if (partialKey in result) {
          result = result[partialKey];
          break;
        }
      }
      result = result[keys[p]];
    } else {
      result = void 0;
    }
  }
  return result;
}

const LIB_NAME = "svelte-i18n";
const DEFINE_MESSAGES_METHOD_NAME = "defineMessages";
const FORMAT_METHOD_NAMES = /* @__PURE__ */ new Set(["format", "_", "t"]);
function isFormatCall(node, imports) {
  if (node.type !== "CallExpression")
    return false;
  let identifier;
  if (node.callee.type === "Identifier") {
    identifier = node.callee;
  }
  if (!identifier || identifier.type !== "Identifier") {
    return false;
  }
  const methodName = identifier.name.slice(1);
  return imports.has(methodName);
}
function isMessagesDefinitionCall(node, methodName) {
  if (node.type !== "CallExpression")
    return false;
  return node.callee && node.callee.type === "Identifier" && node.callee.name === methodName;
}
function getLibImportDeclarations(ast) {
  var _a, _b, _c, _d;
  const bodyElements = [
    ...(_b = (_a = ast.instance) == null ? void 0 : _a.content.body) != null ? _b : [],
    ...(_d = (_c = ast.module) == null ? void 0 : _c.content.body) != null ? _d : []
  ];
  return bodyElements.filter(
    (node) => node.type === "ImportDeclaration" && node.source.value === LIB_NAME
  );
}
function getDefineMessagesSpecifier(decl) {
  return decl.specifiers.find(
    (spec) => "imported" in spec && spec.imported.name === DEFINE_MESSAGES_METHOD_NAME
  );
}
function getFormatSpecifiers(decl) {
  return decl.specifiers.filter(
    (spec) => "imported" in spec && FORMAT_METHOD_NAMES.has(spec.imported.name)
  );
}
function collectFormatCalls(ast) {
  const importDecls = getLibImportDeclarations(ast);
  if (importDecls.length === 0)
    return [];
  const imports = new Set(
    importDecls.flatMap(
      (decl) => getFormatSpecifiers(decl).map((n) => n.local.name)
    )
  );
  if (imports.size === 0)
    return [];
  const calls = [];
  function enter(node) {
    if (isFormatCall(node, imports)) {
      calls.push(node);
      this.skip();
    }
  }
  walk(ast.instance, { enter });
  walk(ast.html, { enter });
  return calls;
}
function collectMessageDefinitions(ast) {
  const definitions = [];
  const defineImportDecl = getLibImportDeclarations(ast).find(
    getDefineMessagesSpecifier
  );
  if (defineImportDecl == null)
    return [];
  const defineMethodName = getDefineMessagesSpecifier(defineImportDecl).local.name;
  const nodeStepInstructions = {
    enter(node) {
      if (isMessagesDefinitionCall(node, defineMethodName) === false)
        return;
      const [arg] = node.arguments;
      if (arg.type === "ObjectExpression") {
        definitions.push(arg);
        this.skip();
      }
    }
  };
  walk(ast.instance, nodeStepInstructions);
  walk(ast.module, nodeStepInstructions);
  return definitions.flatMap(
    (definitionDict) => definitionDict.properties.map((propNode) => {
      if (propNode.type !== "Property") {
        throw new Error(
          `Found invalid '${propNode.type}' at L${propNode.loc.start.line}:${propNode.loc.start.column}`
        );
      }
      return propNode.value;
    })
  );
}
function collectMessages(markup) {
  const ast = parse(markup);
  const calls = collectFormatCalls(ast);
  const definitions = collectMessageDefinitions(ast);
  return [
    ...definitions.map((definition) => getObjFromExpression(definition)),
    ...calls.map((call) => {
      const [pathNode, options] = call.arguments;
      let messageObj;
      if (pathNode.type === "ObjectExpression") {
        messageObj = getObjFromExpression(pathNode);
      } else {
        const node = pathNode;
        const id = node.value;
        if (options && options.type === "ObjectExpression") {
          messageObj = getObjFromExpression(options);
          messageObj.id = id;
        } else {
          messageObj = { id };
        }
      }
      if ((messageObj == null ? void 0 : messageObj.id) == null)
        return null;
      return messageObj;
    })
  ].filter(Boolean);
}
function extractMessages(markup, {
  accumulator = {},
  shallow = false
} = {}) {
  collectMessages(markup).forEach((messageObj) => {
    let defaultValue = messageObj.default;
    if (typeof defaultValue === "undefined") {
      defaultValue = "";
    }
    if (shallow) {
      if (messageObj.id in accumulator)
        return;
      accumulator[messageObj.id] = defaultValue;
    } else {
      if (typeof delve(accumulator, messageObj.id) !== "undefined")
        return;
      deepSet(accumulator, messageObj.id, defaultValue);
    }
  });
  return accumulator;
}

const { readFile, writeFile, mkdir, access, stat } = fs.promises;
const fileExists = (path) => access(path).then(() => true).catch(() => false);
const isDirectory = (path) => stat(path).then((stats) => stats.isDirectory());
function isSvelteError(error, code) {
  return typeof error === "object" && error != null && "message" in error && "code" in error && (code == null || error.code === code);
}
const program = sade("svelte-i18n");
program.command("extract <glob> [output]").describe("extract all message definitions from files to a json").option(
  "-s, --shallow",
  "extract to a shallow dictionary (ids with dots interpreted as strings, not paths)",
  false
).option(
  "--overwrite",
  "overwrite the content of the output file instead of just appending new properties",
  false
).option(
  "-c, --config <dir>",
  'path to the "svelte.config.js" file',
  `${process.cwd()}/svelte.config.js`
).action(async (globStr, output, { shallow, overwrite, config }) => {
  const filesToExtract = (await glob(globStr)).filter(
    (file) => file.match(/\.html|svelte$/i)
  );
  const isConfigDir = await isDirectory(config);
  const resolvedConfigPath = resolve(
    config,
    isConfigDir ? "svelte.config.js" : ""
  );
  if (isConfigDir) {
    console.warn(
      color.yellow(
        `Warning: -c/--config should point to the svelte.config file, not to a directory.
Using "${resolvedConfigPath}".`
      )
    );
  }
  const svelteConfig = await import(resolvedConfigPath).then((mod) => mod.default || mod).catch(() => null);
  let accumulator = {};
  if (output != null && overwrite === false && await fileExists(output)) {
    accumulator = await readFile(output).then((file) => JSON.parse(file.toString())).catch((e) => {
      console.warn(e);
      accumulator = {};
    });
  }
  for await (const filePath of filesToExtract) {
    try {
      const buffer = await readFile(filePath);
      let content = buffer.toString();
      if (svelteConfig == null ? void 0 : svelteConfig.preprocess) {
        const processed = await preprocess(content, svelteConfig.preprocess, {
          filename: filePath
        });
        content = processed.code;
      }
      extractMessages(content, { accumulator, shallow });
    } catch (e) {
      if (isSvelteError(e, "parse-error") && e.message.includes("Unexpected token")) {
        const msg = [
          `Error: unexpected token detected in "${filePath}"`,
          svelteConfig == null && `A svelte config is needed if the Svelte files use preprocessors. Tried to load "${resolvedConfigPath}".`,
          svelteConfig != null && `A svelte config was detected at "${resolvedConfigPath}". Make sure the preprocess step is correctly configured."`
        ].filter(Boolean).join("\n");
        console.error(color.red(msg));
        process.exit(1);
      }
      throw e;
    }
  }
  const jsonDictionary = JSON.stringify(accumulator, null, "  ");
  if (output == null)
    return console.log(jsonDictionary);
  await mkdir(dirname(output), { recursive: true });
  await writeFile(output, jsonDictionary);
});
program.parse(process.argv);
