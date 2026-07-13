-- =============================================================
-- SCHEMA INICIAL (executar apenas uma vez no SQL Editor do Supabase)
-- =============================================================

CREATE TABLE IF NOT EXISTS fila (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data_hora TIMESTAMPTZ NOT NULL DEFAULT now(),
    nome TEXT NOT NULL,
    contato TEXT NOT NULL,
    turma TEXT NOT NULL,
    tema TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Aguardando'
);

CREATE INDEX IF NOT EXISTS idx_fila_status ON fila (status);
CREATE INDEX IF NOT EXISTS idx_fila_data_hora ON fila (data_hora);

ALTER TABLE fila ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Acesso publico para a fila"
    ON fila FOR ALL
    USING (true)
    WITH CHECK (true);


-- =============================================================
-- MIGRAÇÃO (executar apenas se a tabela já existe com o schema antigo)
-- =============================================================
-- ALTER TABLE fila RENAME COLUMN aluno TO nome;
-- ALTER TABLE fila ADD COLUMN contato TEXT NOT NULL DEFAULT '';
-- ALTER TABLE fila ALTER COLUMN id SET DEFAULT gen_random_uuid();
-- ALTER TABLE fila ALTER COLUMN id SET DATA TYPE UUID USING id::uuid;
-- ALTER TABLE fila ALTER COLUMN data_hora SET DEFAULT now();
