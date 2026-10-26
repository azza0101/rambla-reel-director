'use strict';
function registerCatalogHandlers({handle,catalog,getSdk,adapter=require('./day_catalog_resolve')}){
 handle('catalogPreviewFrames',async request=>catalog.previewFrames(await getSdk(),request));
 handle('catalogInventory',async()=>adapter.listDayFolders(await getSdk()));
 handle('catalogAnalyze',async request=>catalog.analyze(await getSdk(),request));
 handle('catalogResume',async request=>catalog.analyze(await getSdk(),request));
 handle('catalogPreviewPublish',async()=>catalog.preview(await getSdk()));
 handle('catalogApplyPublish',async request=>catalog.apply(await getSdk(),request));
 handle('catalogEditMembership',async request=>catalog.edit(request));
 handle('cancelCatalog',()=>catalog.cancel());
}
module.exports={registerCatalogHandlers};
