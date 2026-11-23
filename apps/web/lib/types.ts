export type FieldDef = {
  key: string;
  label: string;
  type: "text" | "date" | "number" | "photo";
  required: boolean;
};

export type Industry = {
  id: string;
  name: string;
  industry_code: number;
  expiry_required: boolean;
  fields: FieldDef[];
  checklist: string[];
};

export type Profile = {
  name: string;
  country: string;
  regulator_numbers: Record<string, string>;
  documents: string[];
  contact_email: string;
};

export type Me = {
  wallet: string;
  profile: Profile | null;
  name_hash: string | null;
  issuer_pda: string;
  status: number | null;
  status_label: string | null;
  registered: boolean;
  is_admin: boolean;
};

export type Config = {
  program_id: string;
  rpc_url: string;
  registry_pda: string;
  web_base_url: string;
};

export type Activity = {
  scans: number;
  scanned_serials: number;
  by_verdict: Record<string, number>;
  flagged_serials: { serial: string; regions: number; scans: number }[];
  batch_alert: boolean;
};

export type Batch = {
  id: number;
  public_code: string;
  status: "draft" | "active" | "recalled";
  industry: string | null;
  industry_name: string | null;
  industry_code: number;
  details: Record<string, string>;
  units: number;
  manufactured_at: string | null;
  expires_at: string | null;
  created_at: number;
  confirmed_at: number | null;
  merkle_root: string;
  details_hash: string;
  batch_pda: string;
  issuer_pda: string;
  tx_signature: string | null;
  verify_base: string;
  labels_pdf: string;
  labels_png: string;
  activity?: Activity;
};

export type Prepared = {
  batch_id: number;
  public_code: string;
  industry_id: string;
  industry_code: number;
  nonce: string;
  merkle_root: string;
  details_hash: string;
  units: number;
  manufactured_at: number;
  expires_at: number;
  issuer_pda: string;
  batch_pda: string;
  authority: string;
  program_id: string;
  registry_pda: string;
};

export type Proof = {
  leaf: string;
  root: string;
  leaf_index: number;
  steps: { sibling: string; left: boolean }[];
};

export type VerifyResult = {
  verdict: string;
  label: string;
  tone: "red" | "amber" | "green";
  message: string;
  reason: string;
  registered_line: string | null;
  product: Record<string, string>;
  field_labels: Record<string, string>;
  issuer: {
    name: string | null;
    label: string;
    verified: boolean;
    status: number | null;
  } | null;
  batch: {
    public_code: string;
    batch_number: string;
    industry_code: number;
    units: number;
    expires_at: string | null;
    manufactured_at: string | null;
    status: string;
  } | null;
  checklist: string[];
  proof: Proof | null;
  verify_path: string | null;
};

export type AdminIssuer = {
  wallet: string;
  issuer_pda: string;
  profile: Profile;
  name_hash: string;
  status: number;
  status_label: string;
  created_at: number;
  verified_at: number;
};
