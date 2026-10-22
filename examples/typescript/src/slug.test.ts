import { test } from "node:test";
import assert from "node:assert/strict";
import { slug } from "./slug.ts";

test("words are joined by one hyphen, in lower case", () => {
  assert.equal(slug("Juniper Bakery Proposal"), "juniper-bakery-proposal");
});

test("punctuation and runs of spaces collapse to one hyphen", () => {
  assert.equal(slug("Q3:  scope, rates & dates!"), "q3-scope-rates-dates");
});

test("accents are dropped, not the letters under them", () => {
  assert.equal(slug("Café Crème"), "cafe-creme");
});

test("nothing but punctuation gives an empty slug", () => {
  assert.equal(slug(" -- "), "");
});
