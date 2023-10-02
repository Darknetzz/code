<?php
/*
    # ────────────────────────────────────────────────────────── #
    #                                                            #
    #    $$\   $$\ $$$$$$$$\ $$$$$$\ $$\       $$$$$$\           #
    #    $$ |  $$ |\__$$  __|\_$$  _|$$ |     $$  __$$\          #
    #    $$ |  $$ |   $$ |     $$ |  $$ |     $$ /  \__|         #
    #    $$ |  $$ |   $$ |     $$ |  $$ |     \$$$$$$\           #
    #    $$ |  $$ |   $$ |     $$ |  $$ |      \____$$\          #
    #    $$ |  $$ |   $$ |     $$ |  $$ |     $$\   $$ |         #
    #    \$$$$$$  |   $$ |   $$$$$$\ $$$$$$$$\\$$$$$$  |         #
    #     \______/    \__|   \______|\________|\______/          #
    #                                                            #
    # ────────────────────────────────────────────────────────── #
    # ----[    General but useful PHP utilities. ]-------------  #
    # ----[    Made with ❤️ by darknetzz         ]-------------  #
    # ----[    https://github.com/Darknetzz/     ]-------------  #
    # ────────────────────────────────────────────────────────── #

    # --------[ Import utils ]--------
    require_once("utils.php");
    use Darknetzz\PHPUtils as Utils;
    $util = new Utils;


    - Slugify
        $string     = "Some test-string_haha :D";
        $slugified  = $util->slugify($string); 
        echo $slugified; # should return "some_test_string_haha"


    - countFunctionParams
        $functionName = "strlen";
        $countParams  = $util->countFunctionParams($functionName);
        echo "$functionName has $countParams params.\n";

    - var_assert
        $variable = "This is set!";
        $variable2= "But this will not be..."; 
        unset($variable2); 
        echo "\$variable: ".$util->var_assert($variable."\n");  should be true    ("This is set!")
        echo "\$variable2:".$util->var_assert($variable2."\n"); should be false   (null)

──────────────────────────────────────────────────────────────────────────────────────────────────────────────
[ END_HOWTO ] ################## [ END_HOWTO ] ################## [ END_HOWTO ] ################## [ END_HOWTO ]
──────────────────────────────────────────────────────────────────────────────────────────────────────────────
*/

namespace Traits;

/* ────────────────────────────────────────────────────────────────────────── */
/*                                 Class Utils                                */
/* ────────────────────────────────────────────────────────────────────────── */
class PHPUtils 
{

    use Strings;
    use Funcs;
    use Vars;
    use Times;
    use Crypto;

    public function __construct() {
        # PHPUtils Class initialized.
    }

}

?>