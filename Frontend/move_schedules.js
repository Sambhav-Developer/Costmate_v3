const fs = require('fs');
let content = fs.readFileSync('src/components/SetupWizardModal.tsx', 'utf-8');

const startIdx = content.indexOf('                          {/* FOOTINGS SCHEDULE */}');
const endIdx = content.indexOf('                        </div>\n                      )}\n\n                      {/* Tab Content: Rooms */}');

if (startIdx === -1 || endIdx === -1) {
  console.log("Could not find start or end block");
  process.exit(1);
}

let schedulesBlock = content.substring(startIdx, endIdx);

// Replace variables
schedulesBlock = schedulesBlock.replaceAll('activeFloor.floorSpecs.footings', 'globalSettings.footings');
schedulesBlock = schedulesBlock.replaceAll('activeFloor.floorSpecs.columns', 'globalSettings.columns');
schedulesBlock = schedulesBlock.replaceAll('activeFloor.floorSpecs.beams', 'globalSettings.beams');

// Improve Column Shape dropdown
const targetShape1 = `{renderGridSelect(col.shape, v => updateStructuralItem('columns', idx, 'shape', v), ['Rectangle', 'Square', 'Circular'])}`;
const replaceShape1 = `<select value={col.shape} onChange={e => updateStructuralItem('columns', idx, 'shape', e.target.value)} className="w-full bg-black/40 border border-white/10 rounded-md px-2 py-1.5 text-xs text-white focus:outline-none focus:border-violet-500"><option>Rectangle</option><option>Square</option><option>Circular</option></select>`;
schedulesBlock = schedulesBlock.replace(targetShape1, replaceShape1);

const targetShape2 = `{renderGridSelect(newColumn.shape, v => setNewColumn({...newColumn, shape: v}), ['Rectangle', 'Square', 'Circular'])}`;
const replaceShape2 = `<select value={newColumn.shape} onChange={e => setNewColumn({...newColumn, shape: e.target.value})} className="w-full bg-black/40 border border-white/10 rounded-md px-2 py-1.5 text-xs text-white focus:outline-none focus:border-violet-500"><option>Rectangle</option><option>Square</option><option>Circular</option></select>`;
schedulesBlock = schedulesBlock.replace(targetShape2, replaceShape2);

// Remove from old place
content = content.substring(0, startIdx) + content.substring(endIdx);

// Insert into new place
const step1EndStr = `                  </div>\n                </div>\n              </div>\n            </div>\n          )}\n\n          {/* STEP 2: Floor Layouts & Details */}`;
const step1EndIdx = content.indexOf(step1EndStr);

if (step1EndIdx === -1) {
  console.log("Could not find step 1 end");
  process.exit(1);
}

const beforeStep1 = content.substring(0, step1EndIdx);
const afterStep1 = content.substring(step1EndIdx + step1EndStr.length - '          {/* STEP 2: Floor Layouts & Details */}'.length);

const insertion = `                  </div>\n                </div>\n\n                {/* GLOBAL SCHEDULES */}\n` + schedulesBlock + `              </div>\n            </div>\n          )}\n\n`;

content = beforeStep1 + insertion + afterStep1;

fs.writeFileSync('src/components/SetupWizardModal.tsx', content, 'utf-8');
console.log("Successfully moved schedules to Step 1.");
