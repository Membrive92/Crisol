export type RuleMatchType = 'exact' | 'contains' | 'starts_with' | 'regex';
export type RuleField = 'concept' | 'description' | 'both';

export interface CategoryRule {
  id: string;
  user_id: string;
  pattern: string;
  match_type: RuleMatchType;
  field: RuleField;
  category_id: string;
  priority: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface CategoryRuleCreateRequest {
  pattern: string;
  match_type: RuleMatchType;
  field: RuleField;
  category_id: string;
  priority?: number;
  enabled?: boolean;
}

export interface CategoryRuleUpdateRequest {
  pattern?: string;
  match_type?: RuleMatchType;
  field?: RuleField;
  category_id?: string;
  priority?: number;
  enabled?: boolean;
}

export interface SeedResult {
  categories_created: number;
  categories_existed: number;
  rules_created: number;
  rules_existed: number;
}
