Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Create form
$form = New-Object System.Windows.Forms.Form
$form.Text = "Terraform HCL Test Prompt Generator"
$form.Size = New-Object System.Drawing.Size(600, 520)
$form.StartPosition = "CenterScreen"

# Provider label and dropdown
$providerLabel = New-Object System.Windows.Forms.Label
$providerLabel.Text = "Select Provider:"
$providerLabel.Location = New-Object System.Drawing.Point(20, 20)
$form.Controls.Add($providerLabel)

$providerDropdown = New-Object System.Windows.Forms.ComboBox
$providerDropdown.Location = New-Object System.Drawing.Point(200, 20)
$providerDropdown.Width = 200
$providerDropdown.Items.AddRange(@("Azure", "GCP"))
$form.Controls.Add($providerDropdown)

# Service label and textbox
$serviceLabel = New-Object System.Windows.Forms.Label
$serviceLabel.Text = "Enter Service Name:"
$serviceLabel.Location = New-Object System.Drawing.Point(20, 70)
$form.Controls.Add($serviceLabel)

$serviceBox = New-Object System.Windows.Forms.TextBox
$serviceBox.Location = New-Object System.Drawing.Point(200, 70)
$serviceBox.Width = 200
$form.Controls.Add($serviceBox)

# Coverage label and textbox
$coverageLabel = New-Object System.Windows.Forms.Label
$coverageLabel.Text = "Target Coverage (%):"
$coverageLabel.Location = New-Object System.Drawing.Point(20, 120)
$form.Controls.Add($coverageLabel)

$coverageBox = New-Object System.Windows.Forms.TextBox
$coverageBox.Location = New-Object System.Drawing.Point(200, 120)
$coverageBox.Width = 200
$form.Controls.Add($coverageBox)

# File selection
$fileLabel = New-Object System.Windows.Forms.Label
$fileLabel.Text = "Select Terraform Files (.tf):"
$fileLabel.Location = New-Object System.Drawing.Point(20, 170)
$form.Controls.Add($fileLabel)

$fileButton = New-Object System.Windows.Forms.Button
$fileButton.Text = "Browse..."
$fileButton.Location = New-Object System.Drawing.Point(200, 170)
$fileButton.Width = 100
$form.Controls.Add($fileButton)

$fileListBox = New-Object System.Windows.Forms.ListBox
$fileListBox.Location = New-Object System.Drawing.Point(20, 210)
$fileListBox.Size = New-Object System.Drawing.Size(540, 100)
$form.Controls.Add($fileListBox)

# Output box
$outputBox = New-Object System.Windows.Forms.TextBox
$outputBox.Multiline = $true
$outputBox.ScrollBars = "Vertical"
$outputBox.Location = New-Object System.Drawing.Point(20, 330)
$outputBox.Size = New-Object System.Drawing.Size(540, 100)
$form.Controls.Add($outputBox)

# Browse action
$fileButton.Add_Click({
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Filter = "Terraform Files (*.tf)|*.tf|All Files (*.*)|*.*"
    $dialog.Multiselect = $true
    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        $fileListBox.Items.Clear()
        $fileListBox.Items.AddRange($dialog.FileNames)
    }
})

# Generate button
$generateButton = New-Object System.Windows.Forms.Button
$generateButton.Text = "Generate Prompt"
$generateButton.Location = New-Object System.Drawing.Point(240, 440)
$form.Controls.Add($generateButton)

$generateButton.Add_Click({
    $provider = $providerDropdown.SelectedItem
    $service = $serviceBox.Text
    $coverage = $coverageBox.Text
    $files = $fileListBox.Items

    if (-not $provider -or -not $service -or -not $coverage -or $files.Count -eq 0) {
        [System.Windows.Forms.MessageBox]::Show("Please fill all fields and select at least one file.")
        return
    }

    $combinedCode = ""
    foreach ($file in $files) {
        $content = Get-Content $file -Raw -ErrorAction SilentlyContinue
        $combinedCode += "`n# File: $file`n$content`n"
    }

    $prompt = @"
You are a Terraform testing expert.

### Objective
Generate **Terraform native `.tftest.hcl` test cases** for **$provider $service** achieving **$coverage% coverage**.

### Test Mode
- Framework: **Terraform native HCL test framework**

### Requirements
- Detect all Terraform resources, variables, and outputs
- Create `plan`, `apply`, and `destroy` test cases using Terraform’s native HCL testing framework
- Output must strictly follow `.tftest.hcl` syntax
- Include assertions for expected resource changes and variable validations

### Files to Analyze
$combinedCode

### Output Structure
## Resource and Variable Summary
[List key resources, variables, and outputs analyzed]

## Generated `.tftest.hcl` Test Code
```hcl
# Example Test Structure
run "plan" {
  command = ["terraform", "plan"]
  assert {
    condition = contains(output.resource_names, "expected_resource")
  }
}

run "apply" {
  command = ["terraform", "apply", "-auto-approve"]
  assert {
    condition = output.resource_status == "created"
  }
}

run "destroy" {
  command = ["terraform", "destroy", "-auto-approve"]
  assert {
    condition = output.destroyed == true
  }
}
```

## Coverage Summary
[Explain how the tests achieve $coverage% coverage]

## Improvement Suggestions
[List improvements for better coverage and validation]
"@

    $outputBox.Text = $prompt
})

# Run form
$form.ShowDialog()
