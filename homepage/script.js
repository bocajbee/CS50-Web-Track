
function hamburgerButton()
{
    // take the current div element passed in on line 30 by element, then store this
    var x = document.getElementById("myLinks");

    // check line 130 of styles.css. If this condition sees if that the element at "myLinks.style.display" is set to "block" as referenced in the CSS style sheet
    // then set "x.style.display to "none", essentialy hiding/closing the hamburger menu
    if (x.style.display === "block")
    {
        x.style.display = "none";
    }
    // otherwise, if it sees "myLinks.style.display" is set to "none", it'll change this to "block", expalnding the hamburger menu
    else
    {
        x.style.display = "block";
    }
}

