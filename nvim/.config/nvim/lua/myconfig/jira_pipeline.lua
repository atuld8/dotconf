local M = {}

function M.run(use_ollama)
  local tmp  = "/tmp/jira_status.sh"
  local base = vim.fn.expand("~/.vim/AI/ollama/jira_status.sh")

  -- current buffer
  local bufname = vim.api.nvim_buf_get_name(0)
  if bufname == "" then
    vim.notify("No file associated with current buffer", vim.log.levels.ERROR)
    return
  end

  local base_name = vim.fn.fnamemodify(bufname, ":t:r")
  local dir       = vim.fn.fnamemodify(bufname, ":p:h")
  local prompt_file = dir .. "/" .. base_name .. ".pmpt"

  if vim.fn.filereadable(prompt_file) == 0 then
    vim.notify("Prompt file not found: " .. prompt_file, vim.log.levels.ERROR)
    return
  end

  -- copy trusted Jira script
  vim.fn.system({ "cp", base, tmp })
  vim.fn.system({ "chmod", "+x", tmp })

  if use_ollama then
    local prompt = vim.fn.system({ "cat", prompt_file })

    local cmd = string.format([[
ollama run mistral <<'EOF'
You are a Jira JQL assistant.
Convert the request into valid Jira JQL only.
No markdown. No explanation. Output JQL only.

%s
EOF
]], prompt)

    local jql = vim.fn.system(cmd)

    if jql == nil or jql == "" then
      vim.notify("Failed to generate JQL from Ollama", vim.log.levels.ERROR)
      return
    end

    -- Run Jira script with generated JQL
    vim.fn.system(
      "tmux split-window -v " ..
      vim.fn.shellescape(tmp .. " " .. vim.fn.shellescape(jql) .. "; read")
    )
  else
    -- fallback: prompt file already contains JQL
    vim.fn.system(
      "tmux split-window -v " ..
      vim.fn.shellescape(tmp .. " \"" .. prompt_file .. "\"; read")
    )
  end
end

return M

