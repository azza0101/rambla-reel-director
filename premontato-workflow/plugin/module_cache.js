'use strict';
const path=require('node:path');
function invalidatePluginModules(cache,root){
 root=path.resolve(root);
 for(const file of Object.keys(cache)){
  const relative=path.relative(root,file);
  if(relative&&!path.isAbsolute(relative)&&relative!=='..'&&!relative.startsWith('..'+path.sep)&&/\.(?:js|cjs|json)$/i.test(file))delete cache[file];
 }
}
module.exports={invalidatePluginModules};
