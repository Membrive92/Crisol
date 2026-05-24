export type ModuleId =
  | 'dashboard'
  | 'personal-finance'
  | 'debt'
  | 'crypto'
  | 'investments'
  | 'real-estate';

export interface AppModule {
  id: ModuleId;
  label: string;
  basePath: string;
  enabled: boolean;
  sections: ModuleSection[];
}

export interface ModuleSection {
  key: string;
  label: string;
  path: string;
}
