-- Clipy Telescope Integration for Neovim
-- Requirements: telescope.nvim, plenary.nvim

local pickers = require("telescope.pickers")
local finders = require("telescope.finders")
local conf = require("telescope.config").values
local actions = require("telescope.actions")
local action_state = require("telescope.actions.state")
local previewers = require("telescope.previewers")
local Job = require("plenary.job")

local M = {
  config = {
    clipy_path = "clipy", -- Default to command in PATH
  }
}

function M.setup(opts)
  M.config = vim.tbl_deep_extend("force", M.config, opts or {})
end

-- Function to run clipy commands
local function run_clipy(args, on_exit, writer)
  Job:new({
    command = M.config.clipy_path,
    args = args,
    writer = writer,
    on_exit = function(j, return_val)
      if return_val == 0 then
        on_exit(j:result())
      end
    end,
  }):start()
end

function M.clipboard_history()
  run_clipy({ "list", "-s" }, function(results)
    vim.schedule(function()
      pickers.new({}, {
        prompt_title = "Clipy History",
        finder = finders.new_table({
          results = results,
        }),
        sorter = conf.generic_sorter({}),
        
        -- Custom previewer to handle multiline text by unescaping '\n' literals.
        previewer = previewers.new_buffer_previewer({
          title = "Clip Content",
          define_preview = function(self, entry, status)
            local unescaped = entry.value:gsub("\\n", "\n")
            local lines = {}
            for line in unescaped:gmatch("([^\n]*)\n?") do
              table.insert(lines, line)
            end
            -- Remove last empty line if it exists
            if lines[#lines] == "" then table.remove(lines) end
            
            vim.api.nvim_buf_set_lines(self.state.bufnr, 0, -1, false, lines)
          end,
        }),

        attach_mappings = function(prompt_bufnr, map)
          -- Default Action: Restores the selection directly to the current Neovim buffer.
          actions.select_default:replace(function()
            local selection = action_state.get_selected_entry()
            actions.close(prompt_bufnr)
            if selection then
              -- Unescape newlines for Neovim buffer
              local unescaped = selection.value:gsub("\\n", "\n")
              local lines = {}
              for line in unescaped:gmatch("([^\n]*)\n?") do
                table.insert(lines, line)
              end
              -- Remove last empty line if it exists
              if #lines > 1 and lines[#lines] == "" then table.remove(lines) end
              
              -- Paste directly into Neovim
              vim.api.nvim_put(lines, "c", true, true)
            end
          end)

          -- Custom Action: Removes the selection from Clipy history and reloads the picker.
          map("i", "<C-d>", function()
            local selection = action_state.get_selected_entry()
            if selection then
              run_clipy({ "delete" }, function()
                -- Reload the picker
                vim.schedule(function()
                  actions.close(prompt_bufnr)
                  M.clipboard_history()
                end)
              end, { selection.value })
            end
          end)

          return true
        end,
      }):find()
    end)
  end)
end

-- Usage: 
-- require('clipy-telescope').clipboard_history()
-- vim.keymap.set("n", "<leader>c", require('clipy-telescope').clipboard_history)

return M
