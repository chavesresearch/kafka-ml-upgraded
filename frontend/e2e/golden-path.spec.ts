// Real click-through E2E coverage - the gap FUTURE.md's former "No
// end-to-end tests" entry described: nothing in the vitest suite
// exercises a real create-model -> create-configuration -> deploy ->
// train -> infer flow. Runs against the real app (real routing, real
// forms, real Monaco editor) with every /api/* call answered by
// mock-backend.ts's small stateful fake - see that file's header for why
// there's no live backend/cluster involved.
import { expect, test } from '@playwright/test'
import { installMockBackend } from './mock-backend'

const MODEL_CODE = `model = tf.keras.Sequential([
    tf.keras.layers.Input((28, 28, 1)),
    tf.keras.layers.Flatten(),
    tf.keras.layers.Dense(128, activation="relu"),
    tf.keras.layers.Dense(10, activation="softmax"),
])
model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])`

// Most fields in these forms (everything outside ModelView/
// ConfigurationView's name/description) render a bare <Label> as a
// sibling of its <Input>, not `htmlFor`-associated with it (confirmed by
// reading DeploymentView.tsx/InferenceView.tsx directly - not an
// accessibility feature to rely on `getByLabel` for). Scoping by the
// shared `.space-y-1.5` wrapper both fields sit in works regardless, and
// keeps working if field order ever changes.
function fieldByLabel(page: import('@playwright/test').Page, labelText: string) {
  return page.locator('.space-y-1\\.5').filter({ has: page.getByText(labelText, { exact: true }) })
}

// Monaco has no test hooks (see frontend/CLAUDE.md's "CodeEditor.tsx"
// entry - it's a hand-rolled wrapper, not a library with a testing API).
// Clicking into `.monaco-editor` focuses its hidden input textarea;
// `keyboard.type` from there is the standard way to drive it in tests.
async function typeIntoCodeEditor(page: import('@playwright/test').Page, labelText: string, text: string) {
  await fieldByLabel(page, labelText).locator('.monaco-editor').click()
  await page.keyboard.type(text)
}

test.describe('golden path: model -> configuration -> deployment -> training -> inference', () => {
  test('a model can be created, deployed, trained, and its result deployed for inference', async ({ page }) => {
    const backend = await installMockBackend(page)
    const runId = Date.now()
    const modelName = `e2e-model-${runId}`
    const configName = `e2e-config-${runId}`

    // -- 1. Create a model -------------------------------------------------
    await page.goto('/models')
    await expect(page.getByRole('heading', { name: 'Models' })).toBeVisible()
    await page.getByRole('link', { name: 'Add a model' }).click()
    await expect(page).toHaveURL(/\/model-create$/)

    await page.locator('#name').fill(modelName)
    await page.locator('[data-slot="radio-group-item"][value="tf"]').click()
    await typeIntoCodeEditor(page, 'Code *', MODEL_CODE)

    const createModelButton = page.getByRole('button', { name: 'Create' })
    await expect(createModelButton).toBeEnabled()
    await createModelButton.click()

    await expect(page).toHaveURL(/\/models$/)
    await expect(page.getByRole('cell', { name: modelName })).toBeVisible()
    expect(backend.models).toHaveLength(1)
    expect(backend.models[0]).toMatchObject({ name: modelName, framework: 'tf' })
    // Not a byte-exact comparison against MODEL_CODE - Monaco's real
    // auto-indent-on-newline behavior reformats whitespace as you type,
    // same as it would for a real user (confirmed by actually running
    // this, not assumed - the raw typed string and Monaco's resulting
    // value differ only in whitespace). What matters here is that real
    // code reached the model, not exact formatting.
    expect(backend.models[0].code).toContain('tf.keras.Sequential')
    expect(backend.models[0].code).toContain('model.compile')
    const modelId = backend.models[0].id

    // -- 2. Create a configuration from it -----------------------------------
    await page.goto('/configurations')
    await page.getByRole('link', { name: 'Add a configuration' }).click()
    await expect(page).toHaveURL(/\/configuration-create$/)

    await page.locator('#name').fill(configName)
    await page.getByRole('combobox').click()
    await page.getByRole('button', { name: `ID${modelId} ${modelName}` }).click()
    await page.keyboard.press('Escape') // close the MultiSelect popover

    const createConfigButton = page.getByRole('button', { name: 'Create' })
    await expect(createConfigButton).toBeEnabled()
    await createConfigButton.click()

    await expect(page).toHaveURL(/\/configurations$/)
    const configCard = page.locator('[data-slot="card"]').filter({ hasText: configName })
    await expect(configCard).toBeVisible()
    expect(backend.configurations).toHaveLength(1)
    const configId = backend.configurations[0].id

    // -- 3. Deploy the configuration ------------------------------------------
    await configCard.locator('[data-slot="dropdown-menu-trigger"]').click()
    await page.getByRole('menuitem', { name: 'Deploy', exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`/deploy/${configId}$`))

    // shadcn's CardTitle renders a plain <div data-slot="card-title">, not
    // a semantic heading element - confirmed by reading card.tsx, not a
    // real getByRole('heading') target the way ModelList's actual <h1> is.
    await expect(page.locator('[data-slot="card-title"]', { hasText: `Deploy configuration ${configName}` })).toBeVisible()
    await fieldByLabel(page, 'Batch size for training *').locator('input').fill('32')
    await fieldByLabel(page, 'TensorFlow Training configuration *').locator('input').fill('epochs=5')
    await fieldByLabel(page, 'GPU Memory usage estimation in GB (Kubernetes Scheduler) *').locator('input').fill('0')

    const deployButton = page.getByRole('button', { name: 'Deploy' })
    await expect(deployButton).toBeEnabled()
    await deployButton.click()

    await expect(page).toHaveURL(/\/deployments$/)
    expect(backend.deployments).toHaveLength(1)
    expect(backend.deployments[0]).toMatchObject({ configuration: configId, batch: 32, tf_kwargs_fit: 'epochs=5' })
    expect(backend.results).toHaveLength(1)
    const resultId = backend.results[0].id

    // -- 4. "Training finishes" - no real cluster runs in CI, so the
    // mock backend's state is advanced directly, the same way a real
    // training Job posting its final metrics back would. -------------------
    backend.results[0].status = 'finished'
    backend.results[0].train_metrics = { accuracy: [0.61, 0.94], loss: [1.1, 0.19] }
    backend.results[0].val_metrics = { accuracy: [0.6, 0.92], loss: [1.2, 0.24] }
    backend.results[0].training_time = 123

    await page.goto('/results')
    await page.getByRole('button', { name: 'Refresh' }).click()
    const resultRow = page.getByRole('row', { name: new RegExp(`^${resultId}\\b`) })
    await expect(resultRow).toBeVisible()
    await expect(resultRow.locator('[aria-label="finished"]')).toBeVisible()

    // Real metrics show up in the info dialog, not just a status icon.
    await resultRow.getByRole('button').first().click() // the Info (metrics) icon is the first action button
    await expect(page.getByRole('dialog')).toContainText('accuracy')
    await expect(page.getByRole('dialog')).toContainText('0.94')
    await page.keyboard.press('Escape')

    // -- 5. Deploy the finished result for inference --------------------------
    await resultRow.getByTitle('Deploy inference').click()
    await expect(page).toHaveURL(new RegExp(`/results/inference/${resultId}$`))

    await fieldByLabel(page, 'Number of replicas *').locator('input').fill('1')
    await fieldByLabel(page, 'Input format of data *').locator('input').fill('RAW')
    await fieldByLabel(page, 'Configuration for input data *')
      .locator('input')
      .fill('{"data_type": "uint8", "label_type": "uint8"}')
    await fieldByLabel(page, 'Kafka topic for input data *').locator('input').fill('e2e-input-topic')
    await fieldByLabel(page, 'Kafka output topic for predictions *').locator('input').fill('e2e-output-topic')
    await fieldByLabel(page, 'GPU Memory usage estimation (Kubernetes Scheduler) *').locator('input').fill('0')

    const deployInferenceButton = page.getByRole('button', { name: 'Deploy' })
    await expect(deployInferenceButton).toBeEnabled()
    await deployInferenceButton.click()

    await expect(page).toHaveURL(/\/inferences$/)
    expect(backend.inferences).toHaveLength(1)
    expect(backend.inferences[0]).toMatchObject({
      model_result: resultId,
      input_topic: 'e2e-input-topic',
      output_topic: 'e2e-output-topic',
    })
    // Connection details (topics, host, etc.) live behind an Info-icon
    // modal, not as plain visible cells - see InferenceList.tsx.
    await page.getByTitle('Connection details').click()
    await expect(page.getByRole('dialog')).toContainText('e2e-input-topic')
    await expect(page.getByRole('dialog')).toContainText('e2e-output-topic')
  })

  test('the model create form rejects an empty submission and shows no console errors', async ({ page }) => {
    const consoleErrors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text())
    })
    await installMockBackend(page)

    await page.goto('/model-create')
    await expect(page.getByRole('button', { name: 'Create' })).toBeDisabled()

    await page.locator('#name').fill('incomplete-model')
    await expect(page.getByRole('button', { name: 'Create' })).toBeDisabled() // no framework/code yet

    await page.locator('[data-slot="radio-group-item"][value="pth"]').click()
    await expect(page.getByRole('button', { name: 'Create' })).toBeDisabled() // still no code

    expect(consoleErrors).toEqual([])
  })

  test('deleting a model removes it from the list', async ({ page }) => {
    const backend = await installMockBackend(page)
    backend.models.push({
      id: 1,
      name: 'to-delete',
      description: '',
      imports: '',
      code: 'model = ...',
      distributed: false,
      father: null,
      framework: 'tf',
    })

    await page.goto('/models')
    await expect(page.getByRole('cell', { name: 'to-delete' })).toBeVisible()

    await page.getByTitle('Delete model').click()
    await page.getByRole('button', { name: 'Confirm' }).click()

    await expect(page.getByRole('cell', { name: 'to-delete' })).not.toBeVisible()
    expect(backend.models).toHaveLength(0)
  })
})
