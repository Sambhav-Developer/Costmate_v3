const fs = require('fs');

let content = fs.readFileSync('src/components/SetupWizardModal.tsx', 'utf-8');

// 1. Update initial global settings
content = content.replace(
`    closingDoorMaterial: 'Flush Door, Teak Wood',
    closingWindowMaterial: 'Aluminum, UPVC',
    staircaseTreadMaterial: 'Granite',
    staircaseRiserMaterial: 'Granite',
    sameMidlanding: 'Yes',
    midlandingMaterial: 'Granite',
    railingMaterial: 'MS (Mild Steel)',`,
''
);

// 2. Update initial floor specs
const floorSpecsTarget = `        staircaseTreadDim: '',
        staircaseRiserDim: '',
        staircaseWidth: '',`;
const floorSpecsReplacement = `        staircaseTreadDim: '',
        staircaseTreadMaterial: 'Granite',
        staircaseRiserDim: '',
        staircaseRiserMaterial: 'Granite',
        staircaseWidth: '',`;
content = content.replace(floorSpecsTarget, floorSpecsReplacement);

// 3. Add to UI for floor specs
const uiTarget = `{renderInput("Tread Dimension", activeFloor.floorSpecs.staircaseTreadDim || '', v => updateFloorSpec('staircaseTreadDim', v), "e.g. 300mm")}
                              {renderInput("Riser Dimension", activeFloor.floorSpecs.staircaseRiserDim || '', v => updateFloorSpec('staircaseRiserDim', v), "e.g. 150mm")}`;

const uiReplacement = `{renderInput("Tread Dimension", activeFloor.floorSpecs.staircaseTreadDim || '', v => updateFloorSpec('staircaseTreadDim', v), "e.g. 300mm")}
                              {renderSelect("Tread Material", activeFloor.floorSpecs.staircaseTreadMaterial || 'Granite', v => updateFloorSpec('staircaseTreadMaterial', v), ['Granite', 'Vitrified', 'Ceramic', 'Marble'])}
                              {renderInput("Riser Dimension", activeFloor.floorSpecs.staircaseRiserDim || '', v => updateFloorSpec('staircaseRiserDim', v), "e.g. 150mm")}
                              {renderSelect("Riser Material", activeFloor.floorSpecs.staircaseRiserMaterial || 'Granite', v => updateFloorSpec('staircaseRiserMaterial', v), ['Granite', 'Vitrified', 'Ceramic', 'Marble'])}`;
content = content.replace(uiTarget, uiReplacement);

// 4. Update stepper array
const stepperTarget = `          {[
            { num: 1, label: 'Global Setup' },
            { num: 2, label: 'Floor Layouts & Details' },
            { num: 3, label: 'Closing Materials' }
          ].map((s, i) => (`;
const stepperReplacement = `          {[
            { num: 1, label: 'Global Setup' },
            { num: 2, label: 'Floor Layouts & Details' }
          ].map((s, i) => (`;
content = content.replace(stepperTarget, stepperReplacement);

// 5. Update footer conditions
content = content.replace(/{step < 3 \? \(/g, '{step < 2 ? (');
content = content.replace(/i < 2 && <div/g, 'i < 1 && <div');

// 6. Delete step 3 block entirely
const step3Start = `          {/* STEP 3: Closing Materials */}`;
const step3End = `          )}

        </div>

        {/* Footer Actions */}`;

const startIdx = content.indexOf(step3Start);
const endIdx = content.indexOf(step3End);
if (startIdx !== -1 && endIdx !== -1) {
  content = content.substring(0, startIdx) + content.substring(endIdx);
}

fs.writeFileSync('src/components/SetupWizardModal.tsx', content, 'utf-8');
console.log('Done refactoring');
