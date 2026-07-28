// Shared types for the Form Editor sub-components

export interface Door {
  type?: string;
  width_m: number;
  height_m: number;
  material: string;
  frame_material?: string;
  count: number;
}

export interface Window {
  type?: string;
  width_m: number;
  height_m: number;
  material: string;
  count: number;
}

export interface QaForm {
  project_name?: string;
  sub_work_name?: string;
  doors?: Door[];
  windows?: Window[];
  [key: string]: any;
}
