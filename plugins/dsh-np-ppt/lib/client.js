/**
 * DSH Web GUI Client Extension for NP-PPT.
 *
 * BUILD NOTE: dsh's client module loader expects a specific bundle shape.
 * The COMPILED output (`lib/client.js`) must self-register via
 * `window.__ModuleLoader__.load({ id, factory })`, expose its extension via
 * `exports.apply`, and `return module.exports`. A bare ES-module `export`
 * will not register and triggers:
 *   "bundle .../client.js loaded without registering \"dsh-np-ppt\" via __ModuleLoader__.load"
 *
 * APPLY NOTE: `apply` receives a Cordis context (`ctx`), not a "runtime".
 * Accessing any Cordis service on `ctx` (e.g. ctx.slots, ctx.locale) requires
 * declaring that service in package.json -> dsh.client.inject; accessing an
 * undeclared service throws "cannot get property \"X\" without inject". This
 * plugin intentionally keeps `apply` a no-op — its 55173 editor surface is
 * driven by the server-side service/tools, not a client command. Add a
 * UI entry later via `ctx.slots.inject(...)` and list the matching runtime
 * packages in `dsh.client.inject` first.
 */
window.__ModuleLoader__.load({
	id: "dsh-np-ppt",
	factory: (require) => {
		var module = { exports: {} };
		var exports = module.exports;

		function apply(ctx) {
			console.log('[dsh-np-ppt] Client extension loaded');
			// Intentional no-op: the PPT visual editor (55173) is launched via
			// the server-side service/tools, not from the client. See APPLY NOTE
			// above before adding any ctx.* usage (declare it in inject first).
		}

		exports.apply = apply;
		exports.default = { apply };
		return module.exports;
	}
});
